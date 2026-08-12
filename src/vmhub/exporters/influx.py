"""InfluxDB exporter — the long-term history the analytics engine regresses over.

Fields the vendor does not report are omitted from the point rather than written as zero.
"""

from __future__ import annotations

from typing import Any

from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from vmhub.analytics.kpi import efficiency_m2_per_min
from vmhub.model.canonical import ConsumablePart, VacuumTelemetry

MEASUREMENT = "vacuum_telemetry"


class InfluxExporter:
    def __init__(self, url: str, token: str, org: str, bucket: str) -> None:
        self.bucket = bucket
        self._client = InfluxDBClientAsync(url=url, token=token, org=org)

    async def publish(self, telemetry: VacuumTelemetry) -> None:
        await self._client.write_api().write(bucket=self.bucket, record=to_point(telemetry))

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
