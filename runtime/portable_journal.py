"""Single-writer standard-library runtime journal for the detached owner."""

import copy
from datetime import datetime, timezone
import json
import math
import os
import stat
import threading

MAX_LINE_BYTES = 65536
EVENT_TYPES = frozenset(
    {
        "runtime_started",
        "device_selected",
        "progress",
        "epoch_completed",
        "artifact_created",
        "runtime_error",
        "pipeline_cancelled",
        "pipeline_completed",
        "process_exited",
        "process_spawn_failed",
    }
)
METRICS = {
    "epoch",
    "train_loss",
    "test_accuracy",
    "train_samples",
    "test_samples",
    "elapsed_seconds",
}


class RuntimeEvent:
    def __init__(self, value):
        self.value = copy.deepcopy(value)

    @property
    def type(self):
        return self.value["type"]

    @property
    def payload(self):
        return self.value["payload"]

    def model_copy(self, *, deep=False):
        return RuntimeEvent(self.value)


def validate_payload(kind, payload):
    if type(payload) is not dict:
        raise ValueError("RUNTIME_PAYLOAD_INVALID")
    if kind == "epoch_completed":
        if set(payload) != METRICS:
            raise ValueError("RUNTIME_METRICS_INVALID")
        for field in ("epoch", "train_samples", "test_samples"):
            if type(payload[field]) is not int or payload[field] < 1:
                raise ValueError("RUNTIME_METRICS_INVALID")
        for field in ("train_loss", "test_accuracy", "elapsed_seconds"):
            value = payload[field]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("RUNTIME_METRICS_INVALID")
        if payload["test_accuracy"] > 1:
            raise ValueError("RUNTIME_METRICS_INVALID")
    json.dumps(payload, allow_nan=False)


class PortableJournal:
    def __init__(self, path, run_id):
        self.run_id = run_id
        self._events = []
        self._mutex = threading.Lock()
        self._failed = False
        self._fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(self._fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o022
            ):
                raise ValueError("RUNTIME_JOURNAL_UNSAFE")
            parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except BaseException:
            os.close(self._fd)
            self._fd = None
            raise

    def append(self, event_type, block_id, payload):
        with self._mutex:
            if self._fd is None or event_type not in EVENT_TYPES:
                raise ValueError("RUNTIME_JOURNAL_INVALID")
            if self._failed:
                raise ValueError("RUNTIME_JOURNAL_WRITE_UNCERTAIN")
            if block_id is not None and (
                type(block_id) is not str or not 1 <= len(block_id) <= 256
            ):
                raise ValueError("RUNTIME_BLOCK_INVALID")
            validate_payload(event_type, payload)
            seq = len(self._events) + 1
            event = {
                "protocolVersion": 1,
                "runId": self.run_id,
                "seq": seq,
                "source": "runtime",
                "sourceSeq": seq,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": event_type,
                "blockId": block_id,
                "payload": copy.deepcopy(payload),
            }
            raw = (
                json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
            ).encode()
            if len(raw) > MAX_LINE_BYTES:
                raise ValueError("RUNTIME_JOURNAL_LIMIT")
            try:
                view = memoryview(raw)
                while view:
                    size = os.write(self._fd, view)
                    if size <= 0:
                        raise OSError("RUNTIME_JOURNAL_WRITE_FAILED")
                    view = view[size:]
                os.fsync(self._fd)
            except BaseException:
                self._failed = True
                raise
            result = RuntimeEvent(event)
            self._events.append(result)
            return result.model_copy(deep=True)

    def after(self, seq):
        with self._mutex:
            return [event.model_copy(deep=True) for event in self._events[seq:]]

    def close(self):
        with self._mutex:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
