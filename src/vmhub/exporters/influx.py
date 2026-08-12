"""InfluxDB exporter — the long-term history the analytics engine regresses over.

Fields the vendor does not report are omitted from the point rather than written as zero.
"""

from __future__ import annotations

from typing import Any

from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from vmhub.analytics.kpi import efficiency_m2_per_min
from vmhub.model.canonical import ConsumablePart, VacuumTelemetry
from vmhub.sessions import SessionRecord

MEASUREMENT = "vacuum_telemetry"
SESSION_MEASUREMENT = "vacuum_session"


class InfluxExporter:
    def __init__(self, url: str, token: str, org: str, bucket: str) -> None:
        self.bucket = bucket
        self._client = InfluxDBClientAsync(url=url, token=token, org=org)

    async def publish(self, telemetry: VacuumTelemetry) -> None:
        await self._client.write_api().write(bucket=self.bucket, record=to_point(telemetry))

    async def publish_session(self, session: SessionRecord) -> None:
        await self._client.write_api().write(bucket=self.bucket, record=session_to_point(session))

    async def close(self) -> None:
        await self._client.close()


def to_point(telemetry: VacuumTelemetry) -> Point:
    point = (
        Point(MEASUREMENT)
        .time(telemetry.observed_at)
        .tag("device_id", telemetry.device.id)
        .tag("vendor", telemetry.device.vendor.value)
        .tag("model", telemetry.device.model or "unknown")
        .tag("status", telemetry.state.status.value)
    )

    fields: dict[str, Any] = {
        "battery_pct": telemetry.state.battery_pct,
        "is_charging": telemetry.state.is_charging,
        "session_area_m2": telemetry.session.area_m2,
        "session_duration_s": telemetry.session.duration_s,
        "session_completed": telemetry.session.completed,
        "efficiency_m2_per_min": efficiency_m2_per_min(telemetry),
        "station_dust_collections": telemetry.station.dust_collections,
        "station_mop_washes": telemetry.station.mop_washes,
    }
    for part in ConsumablePart:
        consumable = getattr(telemetry.consumables, part.value)
        fields[f"consumable_{part.value}_pct"] = consumable.remaining_pct
        fields[f"consumable_{part.value}_h"] = consumable.remaining_h

    for name, value in fields.items():
        if value is not None:
            point = point.field(name, value)

    if telemetry.fault:
        point = point.tag("fault_code", telemetry.fault.code_canonical.value)
        point = point.tag("fault_code_vendor", telemetry.fault.code_vendor or "")

    return point


def session_to_point(session: SessionRecord) -> Point:
    """A closed session, timestamped at its end - one row per run, not per sample."""
    point = (
        Point(SESSION_MEASUREMENT)
        .time(session.ended_at)
        .tag("device_id", session.device_id)
        .tag("vendor", session.vendor.value)
        .tag("model", session.model or "unknown")
        .tag("ended_in", session.ended_in.value)
        .field("observed_duration_s", session.observed_duration_s)
        .field("started_at", session.started_at.isoformat())
    )

    fields: dict[str, Any] = {
        "area_at_start_m2": session.area_at_start_m2,
        "area_at_end_m2": session.area_at_end_m2,
        "vendor_duration_at_start_s": session.vendor_duration_at_start_s,
        "vendor_duration_at_end_s": session.vendor_duration_at_end_s,
        "completed": session.completed,
        "segment_count": len(session.segments) or None,
    }
    for name, value in fields.items():
        if value is not None:
            point = point.field(name, value)

    if session.suction:
        point = point.tag("suction", session.suction.value)
    if session.water_flow:
        point = point.tag("water_flow", session.water_flow.value)
    if session.fault:
        point = point.tag("fault_code", session.fault.code_canonical.value)

    return point
