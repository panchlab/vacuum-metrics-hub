"""Canonical vacuum telemetry model, schema v1.

Two invariants this module enforces:

1. Raw vendor data is never discarded - ``VacuumTelemetry.raw`` keeps the full source
   payload and ``Fault.code_vendor`` keeps the untranslated code.
2. A missing field is ``None``, never ``0``. A vendor that does not report ``mop_washes``
   is not a vendor that performed zero mop washes.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


class Vendor(StrEnum):
    DREAME = "dreame"
    ROBOROCK = "roborock"
    ECOVACS = "ecovacs"
    IROBOT = "irobot"
    XIAOMI = "xiaomi"
    UNKNOWN = "unknown"


class Capability(StrEnum):
    VACUUM = "vacuum"
    MOP = "mop"
    SELF_EMPTY = "self_empty"
    MOP_WASH = "mop_wash"
    MOP_DRY = "mop_dry"
    LIFT = "lift"
    CLIMB = "climb"


class Status(StrEnum):
    IDLE = "idle"
    CLEANING = "cleaning"
    MOPPING = "mopping"
    PAUSED = "paused"
    RETURNING = "returning"
    DOCKED = "docked"
    CHARGING = "charging"
    EMPTYING = "emptying"
    WASHING = "washing"
    DRYING = "drying"
    ERROR = "error"
    UNKNOWN = "unknown"


class Suction(StrEnum):
    QUIET = "quiet"
    STANDARD = "standard"
    STRONG = "strong"
    TURBO = "turbo"


class WaterFlow(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FaultCode(StrEnum):
    STUCK = "stuck"
    BRUSH_TANGLED = "brush_tangled"
    BIN_FULL = "bin_full"
    WATER_EMPTY = "water_empty"
    SENSOR_DIRTY = "sensor_dirty"
    LIDAR_BLOCKED = "lidar_blocked"
    DOCK_LOST = "dock_lost"
    WHEEL_JAMMED = "wheel_jammed"
    DIRTY_WATER_FULL = "dirty_water_full"
    LOW_BATTERY = "low_battery"
    UNKNOWN = "unknown"


class ConsumablePart(StrEnum):
    MAIN_BRUSH = "main_brush"
    SIDE_BRUSH = "side_brush"
    FILTER = "filter"
    MOP_PAD = "mop_pad"
    SENSORS = "sensors"
    DUST_BAG = "dust_bag"


class Device(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable UID, unique across the fleet")
    vendor: Vendor = Vendor.UNKNOWN
    model: str | None = None
    firmware: str | None = None
    capabilities: list[Capability] = Field(default_factory=list)


class State(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status = Status.UNKNOWN
    battery_pct: float | None = Field(default=None, ge=0, le=100)
    is_charging: bool | None = None


class Session(BaseModel):
    """The active cleaning session, or the most recent completed one."""

    model_config = ConfigDict(extra="forbid")

    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_s: int | None = Field(default=None, ge=0)
    area_m2: float | None = Field(default=None, ge=0)
    segments: list[int] = Field(default_factory=list, description="Room segment IDs")
    suction: Suction | None = None
    water_flow: WaterFlow | None = None
    completed: bool | None = Field(
        default=None, description="Whether the robot finished the run or gave up"
    )


class Consumable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remaining_pct: float | None = Field(default=None, ge=0, le=100)
    remaining_h: float | None = Field(default=None, ge=0)
    replaced_at: datetime | None = None


class Consumables(BaseModel):
    model_config = ConfigDict(extra="forbid")

    main_brush: Consumable = Field(default_factory=Consumable)
    side_brush: Consumable = Field(default_factory=Consumable)
    filter: Consumable = Field(default_factory=Consumable)
    mop_pad: Consumable = Field(default_factory=Consumable)
    sensors: Consumable = Field(default_factory=Consumable)
    dust_bag: Consumable = Field(default_factory=Consumable)


class Station(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dust_collections: int | None = Field(default=None, ge=0)
    mop_washes: int | None = Field(default=None, ge=0)
    water_tank_low: bool | None = None
    dirty_water_full: bool | None = None


class Fault(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_canonical: FaultCode = FaultCode.UNKNOWN
    code_vendor: str | None = None
    message: str | None = None


class VacuumTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    observed_at: datetime
    device: Device
    state: State = Field(default_factory=State)
    session: Session = Field(default_factory=Session)
    consumables: Consumables = Field(default_factory=Consumables)
    station: Station = Field(default_factory=Station)
    fault: Fault | None = None
    raw: dict[str, Any] = Field(
        default_factory=dict, description="Untouched source payload from the integration"
    )
