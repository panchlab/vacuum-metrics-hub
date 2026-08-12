"""Prometheus exporter.

Gauges only — every value is a current-state reading. A canonical field the vendor does
not report is left unset rather than exported as zero, so absent data reads as a gap in
Grafana instead of a plausible-looking floor.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, start_http_server

from vmhub.analytics.kpi import efficiency_m2_per_min
from vmhub.model.canonical import ConsumablePart, VacuumTelemetry
from vmhub.sessions import SessionRecord

_DEVICE_LABELS = ["device_id", "vendor", "model"]

BATTERY = Gauge("vmhub_battery_pct", "Battery charge, percent", _DEVICE_LABELS)
IS_CHARGING = Gauge("vmhub_is_charging", "1 while charging", _DEVICE_LABELS)
STATUS = Gauge("vmhub_status", "1 for the active status", [*_DEVICE_LABELS, "status"])
SESSION_AREA = Gauge("vmhub_session_area_m2", "Area cleaned this session", _DEVICE_LABELS)
SESSION_DURATION = Gauge(
    "vmhub_session_duration_seconds", "Duration of this session", _DEVICE_LABELS
)
EFFICIENCY = Gauge(
    "vmhub_efficiency_m2_per_min", "Cleaning throughput of this session", _DEVICE_LABELS
)
CONSUMABLE_PCT = Gauge(
    "vmhub_consumable_remaining_pct", "Consumable life remaining", [*_DEVICE_LABELS, "part"]
)
CONSUMABLE_HOURS = Gauge(
    "vmhub_consumable_remaining_hours", "Consumable life remaining", [*_DEVICE_LABELS, "part"]
)
DUST_COLLECTIONS = Gauge(
    "vmhub_station_dust_collections_total", "Dock auto-empty cycles", _DEVICE_LABELS
)
MOP_WASHES = Gauge("vmhub_station_mop_washes_total", "Dock mop wash cycles", _DEVICE_LABELS)
FAULT = Gauge(
    "vmhub_fault", "1 while the fault is active", [*_DEVICE_LABELS, "code", "vendor_code"]
)

# Sessions are events, so they count up; the gauges describe the most recent one.
SESSIONS_TOTAL = Counter(
    "vmhub_sessions_total", "Cleaning sessions closed", [*_DEVICE_LABELS, "ended_in"]
)
LAST_SESSION_DURATION = Gauge(
    "vmhub_last_session_observed_duration_seconds",
    "Wall-clock duration of the most recent session",
    _DEVICE_LABELS,
)


class PrometheusExporter:
    def __init__(self, port: int = 9464) -> None:
        self.port = port

    def start(self) -> None:
        start_http_server(self.port)

    def publish(self, telemetry: VacuumTelemetry) -> None:
        labels = (
            telemetry.device.id,
            telemetry.device.vendor.value,
            telemetry.device.model or "unknown",
        )

        _set(BATTERY.labels(*labels), telemetry.state.battery_pct)
        _set(IS_CHARGING.labels(*labels), telemetry.state.is_charging)
        STATUS.labels(*labels, telemetry.state.status.value).set(1)

        _set(SESSION_AREA.labels(*labels), telemetry.session.area_m2)
        _set(SESSION_DURATION.labels(*labels), telemetry.session.duration_s)
        _set(EFFICIENCY.labels(*labels), efficiency_m2_per_min(telemetry))

        for part in ConsumablePart:
            consumable = getattr(telemetry.consumables, part.value)
            _set(CONSUMABLE_PCT.labels(*labels, part.value), consumable.remaining_pct)
            _set(CONSUMABLE_HOURS.labels(*labels, part.value), consumable.remaining_h)

        _set(DUST_COLLECTIONS.labels(*labels), telemetry.station.dust_collections)
        _set(MOP_WASHES.labels(*labels), telemetry.station.mop_washes)

        if telemetry.fault:
            FAULT.labels(
                *labels,
                telemetry.fault.code_canonical.value,
                telemetry.fault.code_vendor or "",
            ).set(1)

    def publish_session(self, session: SessionRecord) -> None:
        labels = (session.device_id, session.vendor.value, session.model or "unknown")
        SESSIONS_TOTAL.labels(*labels, session.ended_in.value).inc()
        LAST_SESSION_DURATION.labels(*labels).set(session.observed_duration_s)


def _set(gauge: Gauge, value: float | bool | None) -> None:
    if value is not None:
        gauge.set(float(value))
