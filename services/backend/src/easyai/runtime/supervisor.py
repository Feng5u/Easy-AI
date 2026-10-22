"""Local adapter for the same standard-library supervision core exported remotely."""

from pathlib import Path
from easyai.domain.contracts import Event
from easyai.services.event_journal import EventJournal
from easyai.runtime.managed import ManagedProcess


class ManagedSupervisor(ManagedProcess[Event]):
    def __init__(
        self,
        run_root: Path,
        run_id: str,
        argv: list[str],
        cwd: Path,
        environment: dict[str, str] | None = None,
        cancel_grace: float = 0.5,
        *,
        max_log_bytes: int | None = None,
        inherit_environment: bool = True,
    ):
        super().__init__(
            run_root,
            run_id,
            argv,
            cwd,
            environment,
            cancel_grace,
            journal_factory=lambda path, identity: EventJournal(path, identity, "runtime"),
            max_log_bytes=max_log_bytes,
            inherit_environment=inherit_environment,
        )
