"""Portable wrapper: preserve tracebacks and emit structured runtime failures."""

from pathlib import Path
import runpy
import sys
import traceback

from easyai_runtime import PipelineCancelled, emit_event


def main():
    try:
        runpy.run_path(str(Path(__file__).with_name("train.py")), run_name="__main__")
    except PipelineCancelled as error:
        if not getattr(error, "_easyai_event_reported", False):
            emit_event("pipeline_cancelled", None, {"message": str(error)})
        return 130
    except Exception as error:
        frames = traceback.extract_tb(error.__traceback__)
        training_frames = [frame for frame in frames if Path(frame.filename).name == "train.py"]
        frame = training_frames[-1] if training_frames else None
        if not getattr(error, "_easyai_event_reported", False):
            emit_event(
                "runtime_error",
                None,
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
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
