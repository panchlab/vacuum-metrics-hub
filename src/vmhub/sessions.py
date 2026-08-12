"""Session tracking: turn a stream of telemetry snapshots into cleaning-session records.

Analytics like efficiency drift and consumable burn rate regress over *sessions*, not over
point-in-time samples, so something has to decide where one run ends and the next begins.

The rule is deliberately one sentence: a session is open while the status is ``cleaning`` or
``mopping``, ``paused`` holds it open, and any other status closes it. A robot that returns
to the dock to recharge mid-run therefore produces two records rather than one - see
docs/adr/0002-session-boundaries.md for why that is the honest split.

This tracker does not recompute area or duration. The vendor already reports both, and vmhub
is a normalization layer, not a reimplementation of the robot. What the tracker adds is the
*moment* to read those counters - it keeps the last sample seen while the session was open,
so the values are captured before the robot resets them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from vmhub.model.canonical import (
    Fault,
    Status,
    Suction,
    VacuumTelemetry,
    Vendor,
    WaterFlow,
)

ACTIVE_STATUSES = frozenset({Status.CLEANING, Status.MOPPING})


class SessionRecord(BaseModel):
    """One contiguous run of cleaning, closed and ready to persist."""

    model_config = ConfigDict(extra="forbid")

    device_id: str
    vendor: Vendor
    model: str | None = None

    started_at: datetime
    ended_at: datetime
    observed_duration_s: float = Field(
        description="Wall clock from the first active sample to the sample that closed the "
        "session. An upper bound, since it is limited by how often Home Assistant updates."
    )
    ended_in: Status = Field(description="The status that closed the session")

    # The vendor's own counters, read at both ends of the session. Whether the session's area
    # is `area_at_end_m2` or `area_at_end_m2 - area_at_start_m2` depends on whether the vendor
    # reports a per-session gauge or a lifetime counter - which real hardware will settle. Both
    # readings are stored so the answer is a subtraction rather than a re-run.
    area_at_start_m2: float | None = None
    area_at_end_m2: float | None = None
    vendor_duration_at_start_s: float | None = None
    vendor_duration_at_end_s: float | None = None

    segments: list[int] = Field(default_factory=list)
    suction: Suction | None = None
    water_flow: WaterFlow | None = None
    completed: bool | None = Field(
        default=None,
        description="Only ever set if the vendor reports it. Inferring it from 'reached the "
        "dock' would be a guess, and a guessed field is not data.",
    )
    fault: Fault | None = None


@dataclass
class _OpenSession:
    first: VacuumTelemetry
    last: VacuumTelemetry


class SessionTracker:
    """Stateful, one open session per device.

    State lives in memory: a restart loses any session in flight. Persisting it would mean
    dragging a state store into the collector for the sake of a single record, which is not a
    trade v0.2 needs to make.
    """

    def __init__(self) -> None:
        self._open: dict[str, _OpenSession] = {}

    def observe(self, telemetry: VacuumTelemetry) -> SessionRecord | None:
        """Feed one telemetry snapshot in; get a record back when a session just closed."""
        device_id = telemetry.device.id
        open_session = self._open.get(device_id)

        if telemetry.state.status in ACTIVE_STATUSES:
            if open_session is None:
                self._open[device_id] = _OpenSession(first=telemetry, last=telemetry)
            else:
                open_session.last = telemetry
            return None

        if open_session is None or telemetry.state.status is Status.PAUSED:
            return None

        del self._open[device_id]
        return _close(open_session, telemetry)


def _close(session: _OpenSession, closing: VacuumTelemetry) -> SessionRecord:
    first, last = session.first, session.last
    return SessionRecord(
        device_id=last.device.id,
        vendor=last.device.vendor,
        model=last.device.model,
        started_at=first.observed_at,
        ended_at=closing.observed_at,
        observed_duration_s=(closing.observed_at - first.observed_at).total_seconds(),
        ended_in=closing.state.status,
        area_at_start_m2=first.session.area_m2,
        area_at_end_m2=last.session.area_m2,
        vendor_duration_at_start_s=first.session.duration_s,
        vendor_duration_at_end_s=last.session.duration_s,
        segments=last.session.segments,
        suction=last.session.suction,
        water_flow=last.session.water_flow,
        completed=last.session.completed,
        fault=closing.fault,
    )
