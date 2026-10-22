"""Portable wrapper: preserve tracebacks and emit structured runtime failures."""

from pathlib import Path
import runpy
import sys
import traceback

from easyai_runtime import PipelineCancelled, emit_event, failure_payload


def main():
    try:
        runpy.run_path(str(Path(__file__).with_name("train.py")), run_name="__main__")
    except PipelineCancelled as error:
        if not getattr(error, "_easyai_event_reported", False):
            emit_event("pipeline_cancelled", None, {"message": str(error)})
        return 130
    except Exception as error:
        if not getattr(error, "_easyai_event_reported", False):
            emit_event("runtime_error", None, failure_payload(error))
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
