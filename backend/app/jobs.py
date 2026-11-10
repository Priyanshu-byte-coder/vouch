"""In-memory background jobs with an event log that SSE clients can replay and follow."""

import asyncio
import time
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .models import Report

MAX_JOBS = 200         # oldest finished jobs are dropped beyond this
MAX_RUNNING = 3        # concurrent pipeline runs


@dataclass
class Job:
    id: str
    kind: str
    label: str
    status: str = "queued"  # queued | running | done | error
    created: float = field(default_factory=time.time)
    events: list[dict] = field(default_factory=list)
    report: Report | None = None
    error: str | None = None
    _changed: asyncio.Condition = field(default_factory=asyncio.Condition, repr=False)

    async def emit(self, kind: str, data: dict) -> None:
        async with self._changed:
            self.events.append({"id": len(self.events), "event": kind, "data": data})
            self._changed.notify_all()

    async def wait_for_events(self, after: int, timeout: float = 15.0) -> None:
        async with self._changed:
            if len(self.events) > after or self.status in ("done", "error"):
                return
            try:
                await asyncio.wait_for(self._changed.wait(), timeout)
            except asyncio.TimeoutError:
                pass

    def summary(self) -> dict[str, Any]:
        refs = [e["data"] for e in self.events if e["event"] == "ref_done"]
        parsed = next((e["data"] for e in self.events if e["event"] == "parsed"), {})
        return {"id": self.id, "kind": self.kind, "label": self.label, "status": self.status, "error": self.error,
                "created": self.created, "n_refs": parsed.get("n_refs"), "done_refs": len(refs),
                "report": self.report.model_dump(mode="json") if self.report else None,
                "partial": None if self.report else sorted(refs, key=lambda r: r["idx"])}


class JobStore:
    def __init__(self) -> None:
        self.jobs: "OrderedDict[str, Job]" = OrderedDict()
        self._slots = asyncio.Semaphore(MAX_RUNNING)

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def start(self, kind: str, label: str, work: Callable[[Job], Awaitable[Report]]) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, label=label)
        self.jobs[job.id] = job
        while len(self.jobs) > MAX_JOBS:
            oldest = next(iter(self.jobs.values()))
            if oldest.status in ("queued", "running"):
                break
            self.jobs.popitem(last=False)
        asyncio.create_task(self._run(job, work))
        return job

    async def _run(self, job: Job, work: Callable[[Job], Awaitable[Report]]) -> None:
        async with self._slots:
            job.status = "running"
            await job.emit("status", {"status": "running"})
            try:
                job.report = await work(job)
                job.status = "done"
                await job.emit("report", job.report.model_dump(mode="json"))
            except Exception as e:  # noqa: BLE001 - surface any pipeline failure to the client
                job.status, job.error = "error", f"{type(e).__name__}: {e}"[:500]
                await job.emit("error", {"error": job.error})
