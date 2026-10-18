"""Portable standard-library-only protocol and file helpers for exported bundles.

This module deliberately contains no model, dataset or training implementation.
"""

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import tempfile
import threading
import traceback
from uuid import uuid4

PREFIX = "@@EASYAI_EVENT@@"
METRIC_FIELDS = (
    "epoch",
    "train_loss",
    "test_accuracy",
    "train_samples",
    "test_samples",
    "elapsed_seconds",
)


class PipelineCancelled(Exception):
    """A cooperative cancellation request for this run."""


def emit_event(event_type, block_id, payload):
    event = {"type": event_type, "blockId": block_id, "payload": payload}
    serialized = json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > 65536:
        raise ValueError("Runtime event exceeds 64 KiB")
    print(PREFIX + serialized, flush=True)
    return event


def _relative(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Invalid artifact path")
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts:
        raise ValueError("Artifact path must stay within the run directory")
    if not path.parts or path.parts[0] != "outputs":
        raise ValueError("Artifacts must be below outputs/")
    if any(len(part.encode("utf-8")) > 255 for part in path.parts):
        raise ValueError("Artifact component exceeds UTF-8 byte budget")
    return path


class RunContext:
    def __init__(
        self,
        data_root,
        output_root,
        seed,
        execution_mode,
        num_workers,
        application_mode=False,
        run_id=None,
    ):
        if type(seed) is not int or not 0 <= seed <= 4294967295:
            raise ValueError("Invalid seed")
        if execution_mode not in ("quick", "full"):
            raise ValueError("Invalid execution mode")
        if type(num_workers) is not int or not 0 <= num_workers <= 16:
            raise ValueError("Invalid worker count")
        self.data_root = Path(data_root).resolve(strict=True)
        if not self.data_root.is_dir():
            raise ValueError("Data root must be a directory")
        target = Path(output_root)
        if target.is_symlink():
            raise ValueError("Run root cannot be a symlink")
        if application_mode:
            if not target.is_dir():
                raise ValueError("Configured run root must already exist")
        else:
            target.mkdir(parents=True, exist_ok=False)
        self.output_root = target.resolve(strict=True)
        self.seed = seed
        self.execution_mode = execution_mode
        self.num_workers = num_workers
        self.application_mode = application_mode
        self.run_id = run_id or str(uuid4())
        self._thread = threading.get_ident()
        self._seq = 0
        self._artifacts = []
        self._epochs = set()
        self._figure_keys = {}
        self._closed = False
        if not application_mode:
            for directory in ("logs", "metrics"):
                (self.output_root / directory).mkdir(exist_ok=False)
            with (self.output_root / "metrics/epochs.csv").open(
                "x", newline="", encoding="utf-8"
            ) as stream:
                csv.DictWriter(stream, fieldnames=METRIC_FIELDS).writeheader()
            self._atomic_json("artifacts.json", [])

    @classmethod
    def from_cli(cls, default_seed=42, default_execution_mode="full"):
        parser = argparse.ArgumentParser(
            description="Run an exported Easy-AI code bundle; data is never downloaded."
        )
        parser.add_argument("--config", type=Path)
        parser.add_argument("--data-root", type=Path)
        parser.add_argument("--output-dir", type=Path)
        parser.add_argument("--seed", type=int)
        args = parser.parse_args()
        if args.config:
            if args.data_root is not None or args.output_dir is not None or args.seed is not None:
                parser.error("--config cannot be combined with standalone flags")
            raw = args.config.read_bytes()
            if len(raw) > 65536:
                raise ValueError("Run config too large")
            config = json.loads(raw)
            if not isinstance(config, dict) or config.get("configVersion") != 1:
                raise ValueError("Unsupported run config")
            if config.get("executionMode") != default_execution_mode:
                raise ValueError("Run config execution mode does not match compiled code")
            return cls(
                config["dataRoot"],
                config["runRoot"],
                config["seed"],
                default_execution_mode,
                config["numWorkers"],
                True,
                config["runId"],
            )
        if args.data_root is None or args.output_dir is None:
            parser.error("Supply both --data-root and --output-dir, or --config")
        workers = 2 if platform.system() == "Linux" else 0
        return cls(
            args.data_root,
            args.output_dir,
            default_seed if args.seed is None else args.seed,
            default_execution_mode,
            workers,
        )

    def _assert_owner(self):
        if self._closed or threading.get_ident() != self._thread:
            raise RuntimeError("Only the active runtime main thread may write events")

    def _atomic_json(self, relative, value):
        destination = self.output_root / relative
        descriptor, temporary = tempfile.mkstemp(prefix=".easyai-", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def emit(self, event_type, block_id, payload):
        self._assert_owner()
        if event_type == "epoch_completed":
            if set(payload) != set(METRIC_FIELDS):
                raise ValueError("Invalid epoch metric fields")
            epoch = payload["epoch"]
            if type(epoch) is not int or epoch < 1 or epoch in self._epochs:
                raise ValueError("Invalid or repeated epoch")
            for field in METRIC_FIELDS[1:]:
                value = payload[field]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < 0
                ):
                    raise ValueError("Invalid finite metric")
            if not 0 <= payload["test_accuracy"] <= 1:
                raise ValueError("Accuracy must be a fraction")
            if any(
                type(payload[field]) is not int or payload[field] <= 0
                for field in ("train_samples", "test_samples")
            ):
                raise ValueError("Sample counts must be positive integers")
            self._epochs.add(epoch)
        event = emit_event(event_type, block_id, payload)
        if not self.application_mode:
            self._seq += 1
            saved = dict(
                event,
                protocolVersion=1,
                runId=self.run_id,
                seq=self._seq,
                source="runtime",
                sourceSeq=self._seq,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            with (self.output_root / "logs/events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(saved, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
            if event_type == "epoch_completed":
                with (self.output_root / "metrics/epochs.csv").open(
                    "a", newline="", encoding="utf-8"
                ) as stream:
                    csv.DictWriter(stream, fieldnames=METRIC_FIELDS).writerow(payload)

    def check_cancelled(self):
        self._assert_owner()
        request = self.output_root / "cancel.request.json"
        if request.is_symlink():
            raise ValueError("Cancellation request cannot be a symlink")
        if request.exists():
            raw = request.read_bytes()
            if len(raw) > 4096:
                raise ValueError("Cancellation request too large")
            payload = json.loads(raw)
            if payload.get("runId") == self.run_id:
                raise PipelineCancelled("Run cancellation requested")

    def _artifact_path(self, relative, create=False):
        path = _relative(relative)
        current = self.output_root
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("Symlinks are forbidden in artifact paths")
        destination = self.output_root.joinpath(*path.parts)
        # Validate the actual absolute target before creating directories/files.
        # POSIX limits are measured in encoded bytes, including the trailing NUL.
        if hasattr(os, "pathconf"):
            name_limit = os.pathconf(self.output_root, "PC_NAME_MAX")
            path_limit = os.pathconf(self.output_root, "PC_PATH_MAX")
            if (name_limit > 0 and any(len(os.fsencode(p)) > name_limit for p in path.parts)) or (
                path_limit > 0 and len(os.fsencode(destination)) + 1 > path_limit
            ):
                raise ValueError("Artifact exceeds physical filesystem path budget")
        if create:
            destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.resolve().is_relative_to(self.output_root):
            raise ValueError("Artifact escapes run directory")
        return destination

    @contextmanager
    def atomic_target(self, relative):
        self._assert_owner()
        destination = self._artifact_path(relative, create=True)
        if destination.exists():
            raise FileExistsError("Refusing to overwrite a previous artifact")
        # PyTorch's zip writer rejects a dot-prefixed basename. Keep the suffix
        # for file serializers, while publication remains atomic and exclusive.
        descriptor, temporary = tempfile.mkstemp(
            prefix="easyai-part-", suffix=destination.suffix, dir=destination.parent
        )
        os.close(descriptor)
        try:
            yield Path(temporary)
            self._artifact_path(relative)
            with open(temporary, "rb") as stream:
                os.fsync(stream.fileno())
            # Hard-link publishes complete bytes without replacing an existing artifact.
            os.link(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def figure_path(self, figure_id, phase, epoch=None, logical=None):
        if phase not in ("before", "epoch_end", "after"):
            raise ValueError("Invalid figure phase")
        if phase == "epoch_end" and (type(epoch) is not int or not 1 <= epoch <= 10000):
            raise ValueError("Epoch figure requires a positive epoch")
        block_key = hashlib.sha256(figure_id.encode("utf-8")).hexdigest()[:16]
        if block_key in self._figure_keys and self._figure_keys[block_key] != figure_id:
            raise ValueError("Figure block key collision")
        self._figure_keys[block_key] = figure_id
        suffix = f"epoch-{epoch:04d}" if phase == "epoch_end" else phase
        if logical is None:
            physical = f"outputs/figures/{block_key}/{suffix}.png"
            self._artifact_path(physical)
            return physical
        if (
            not isinstance(logical, str)
            or len(logical) > 256
            or any(ord(c) < 32 or c in ':*?"<>|' for c in logical)
        ):
            raise ValueError("Invalid logical figure path")
        path = PurePosixPath(logical)
        if path.parts and path.parts[0] != "outputs":
            path = PurePosixPath("outputs") / path
        if len(str(path)) > 256:
            raise ValueError("Invalid logical figure path")
        path = _relative(str(path))
        if path.suffix.lower() != ".png":
            raise ValueError("Figures require .png paths")
        if len(path.stem.encode("utf-8")) + 31 + len(path.suffix.encode("utf-8")) > 255:
            raise ValueError("Figure name exceeds final UTF-8 byte budget")
        physical = str(path.with_name(f"{path.stem}__{block_key}__{suffix}.png"))
        self._artifact_path(physical)
        return physical

    def artifact(self, relative, kind, producer, contributors, phase=None, epoch=None):
        self._assert_owner()
        destination = self._artifact_path(relative)
        if not destination.is_file():
            raise ValueError("Artifact must be a complete regular file")
        digest = hashlib.sha256()
        with destination.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        record = {
            "artifactId": str(uuid4()),
            "runId": self.run_id,
            "kind": kind,
            "relativePath": relative,
            "mimeType": "image/png" if kind == "figure" else "application/octet-stream",
            "sizeBytes": destination.stat().st_size,
            "sha256": digest.hexdigest(),
            "producerBlockId": producer,
            "contributorBlockIds": contributors,
            "syncState": "ready",
        }
        if phase is not None:
            record["phase"] = phase
        if epoch is not None:
            record["epoch"] = epoch
        self.emit("artifact_created", producer, record)
        if not self.application_mode:
            self._artifacts.append(record)
            self._atomic_json("artifacts.json", self._artifacts)
        return record

    def report_failure(self, error, block_id=None):
        """Persist failures before closing; entry.py prints the original traceback."""
        if isinstance(error, PipelineCancelled):
            self.emit("pipeline_cancelled", block_id, {"message": str(error)[:4096]})
        else:
            frames = traceback.extract_tb(error.__traceback__)
            training_frames = [frame for frame in frames if Path(frame.filename).name == "train.py"]
            frame = training_frames[-1] if training_frames else None
            self.emit(
                "runtime_error",
                block_id,
                {
                    "exceptionType": type(error).__name__,
                    "message": str(error)[:4096],
                    "variableName": getattr(error, "name", None)
                    if isinstance(error, NameError)
                    else None,
                    "file": "train.py" if frame else None,
                    "line": frame.lineno if frame else None,
                },
            )
        error._easyai_event_reported = True

    def close(self):
        self._assert_owner()
        self._closed = True
