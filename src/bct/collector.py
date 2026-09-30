from dataclasses import dataclass
from typing import Callable, Iterable, Protocol


@dataclass(frozen=True)
class SourceRecord:
    external_id: str | None
    content: bytes
    media_type: str = "application/octet-stream"


class Collector(Protocol):
    """Future vendor adapters implement only this contract; core owns persistence."""
    @property
    def name(self) -> str: ...

    def collect(self, checkpoint: str | None = None) -> Iterable[SourceRecord]: ...


class MalformedRecord(ValueError):
    pass


@dataclass
class RunProgress:
    saved: int = 0
    duplicates: int = 0
    updated: int = 0


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    saved: int = 0
    duplicates: int = 0
    failed: int = 0
    error: str | None = None
    updated: int = 0


def execute_run(session_factory, collector: str, key: str,
                work: Callable[[RunProgress], None]) -> RunResult:
    """Small shared run lifecycle for serial collectors. Each adapter persists its own rows."""
    from .core import get_or_create_run, transition_run
    from .models import CollectorRun

    with session_factory.begin() as session:
        run = get_or_create_run(session, collector, key)
        run_id = run.id
        if run.status == "succeeded":
            return RunResult(run_id, "succeeded")
        if run.status == "running":
            transition_run(session, run, "failed", "interrupted previous run")
        transition_run(session, run, "running")
    progress = RunProgress()
    try:
        work(progress)
        with session_factory.begin() as session:
            transition_run(session, session.get(CollectorRun, run_id), "succeeded")
        return RunResult(run_id, "succeeded", progress.saved, progress.duplicates,
                         updated=progress.updated)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"[:1000]
        with session_factory.begin() as session:
            transition_run(session, session.get(CollectorRun, run_id), "failed", reason)
        return RunResult(run_id, "failed", progress.saved, progress.duplicates, 1,
                         reason, progress.updated)
