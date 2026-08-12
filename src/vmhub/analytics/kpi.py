"""Per-session KPIs derived from canonical telemetry.

Everything here is a pure function of a single telemetry snapshot. Metrics that need
history (efficiency_drift, consumable_burn_rate, MTBF) land in v0.4 once the time-series
store has enough sessions to be worth regressing over — see docs/metrics.md.
"""

from __future__ import annotations

from vmhub.model.canonical import VacuumTelemetry


def efficiency_m2_per_min(telemetry: VacuumTelemetry) -> float | None:
    """Cleaning throughput of the current session, or None if it cannot be computed."""
    session = telemetry.session
    if not session.area_m2 or not session.duration_s:
        return None
    return session.area_m2 / (session.duration_s / 60)
