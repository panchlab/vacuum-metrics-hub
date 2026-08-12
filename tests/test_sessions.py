from datetime import datetime, timedelta

import pytest

from vmhub.model.canonical import (
    Device,
    Fault,
    FaultCode,
    Session,
    State,
    Status,
    VacuumTelemetry,
    Vendor,
)
from vmhub.sessions import SessionTracker

START = datetime.fromisoformat("2026-08-12T09:00:00+00:00")


def sample(
    status: Status,
    *,
    minute: int = 0,
    area: float | None = None,
    duration_s: float | None = None,
    device_id: str = "vacuum.x50_ultra",
    fault: Fault | None = None,
) -> VacuumTelemetry:
    return VacuumTelemetry(
        observed_at=START + timedelta(minutes=minute),
        device=Device(id=device_id, vendor=Vendor.DREAME, model="X50 Ultra"),
        state=State(status=status),
        session=Session(area_m2=area, duration_s=duration_s),
        fault=fault,
    )


@pytest.fixture
def tracker() -> SessionTracker:
    return SessionTracker()


def test_a_run_produces_one_record_when_it_docks(tracker: SessionTracker) -> None:
    assert tracker.observe(sample(Status.CLEANING, minute=0, area=0)) is None
    assert tracker.observe(sample(Status.CLEANING, minute=20, area=30)) is None

    record = tracker.observe(sample(Status.DOCKED, minute=30))

    assert record is not None
    assert record.device_id == "vacuum.x50_ultra"
    assert record.ended_in is Status.DOCKED
    assert record.observed_duration_s == 30 * 60


def test_pause_does_not_close_the_session(tracker: SessionTracker) -> None:
    tracker.observe(sample(Status.CLEANING, minute=0))
    assert tracker.observe(sample(Status.PAUSED, minute=5)) is None
    assert tracker.observe(sample(Status.CLEANING, minute=10)) is None

    record = tracker.observe(sample(Status.DOCKED, minute=15))

    assert record is not None
    assert record.observed_duration_s == 15 * 60


def test_counters_are_read_at_both_ends(tracker: SessionTracker) -> None:
    """The open question of gauge-vs-lifetime is answerable from the record itself."""
    tracker.observe(sample(Status.CLEANING, minute=0, area=12.0, duration_s=60))
    tracker.observe(sample(Status.CLEANING, minute=20, area=42.6, duration_s=1260))

    record = tracker.observe(sample(Status.DOCKED, minute=25, area=0))

    assert record is not None
    assert record.area_at_start_m2 == 12.0
    assert record.area_at_end_m2 == 42.6  # last active sample, not the post-dock reset
    assert record.vendor_duration_at_start_s == 60
    assert record.vendor_duration_at_end_s == 1260


def test_mid_run_recharge_produces_two_records(tracker: SessionTracker) -> None:
    """ADR-0002: bursts of active cleaning are not glued back together."""
    tracker.observe(sample(Status.CLEANING, minute=0))
    first = tracker.observe(sample(Status.CHARGING, minute=30))

    tracker.observe(sample(Status.CLEANING, minute=90))
    second = tracker.observe(sample(Status.DOCKED, minute=110))

    assert first is not None and second is not None
    assert first.ended_in is Status.CHARGING
    assert second.ended_in is Status.DOCKED
    assert second.started_at == START + timedelta(minutes=90)


def test_an_unmapped_status_closes_rather_than_swallows(tracker: SessionTracker) -> None:
    tracker.observe(sample(Status.CLEANING, minute=0))
    record = tracker.observe(sample(Status.UNKNOWN, minute=10))

    assert record is not None
    assert record.ended_in is Status.UNKNOWN


def test_a_failed_run_carries_the_fault(tracker: SessionTracker) -> None:
    tracker.observe(sample(Status.CLEANING, minute=0))
    fault = Fault(code_canonical=FaultCode.STUCK, code_vendor="6")

    record = tracker.observe(sample(Status.ERROR, minute=8, fault=fault))

    assert record is not None
    assert record.ended_in is Status.ERROR
    assert record.fault is not None
    assert record.fault.code_canonical is FaultCode.STUCK


def test_completed_is_never_inferred(tracker: SessionTracker) -> None:
    """Reaching the dock is not the vendor telling us the run finished."""
    tracker.observe(sample(Status.CLEANING, minute=0))
    record = tracker.observe(sample(Status.DOCKED, minute=20))

    assert record is not None
    assert record.completed is None


def test_idle_without_an_open_session_emits_nothing(tracker: SessionTracker) -> None:
    assert tracker.observe(sample(Status.DOCKED, minute=0)) is None
    assert tracker.observe(sample(Status.IDLE, minute=5)) is None


def test_devices_are_tracked_independently(tracker: SessionTracker) -> None:
    tracker.observe(sample(Status.CLEANING, minute=0, device_id="vacuum.upstairs"))
    tracker.observe(sample(Status.CLEANING, minute=2, device_id="vacuum.downstairs"))

    assert tracker.observe(sample(Status.DOCKED, minute=10, device_id="vacuum.upstairs"))
    assert tracker.observe(sample(Status.DOCKED, minute=40, device_id="vacuum.downstairs"))


def test_a_closed_session_does_not_close_twice(tracker: SessionTracker) -> None:
    tracker.observe(sample(Status.CLEANING, minute=0))
    assert tracker.observe(sample(Status.DOCKED, minute=10)) is not None
    assert tracker.observe(sample(Status.DOCKED, minute=11)) is None
