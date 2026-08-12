"""Declarative YAML adapters: vendor attributes → canonical telemetry.

An adapter is data, not code, so that adding a vacuum is a PR against a YAML file.
See ``adapters/_template.yaml`` for the format.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from vmhub.model.canonical import (
    Capability,
    Device,
    Fault,
    FaultCode,
    Status,
    VacuumTelemetry,
    Vendor,
)

TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "min_to_s": lambda v: float(v) * 60,
    "h_to_s": lambda v: float(v) * 3600,
    "s_to_min": lambda v: float(v) / 60,
    "cm2_to_m2": lambda v: float(v) / 10_000,
    "fraction_to_pct": lambda v: float(v) * 100,
    "to_int": int,
    "to_float": float,
    "to_bool": bool,
}


class AdapterError(Exception):
    pass


def _dig(payload: dict[str, Any], path: str) -> Any:
    """Resolve a dotted path like ``attributes.battery_level``, or None if absent."""
    current: Any = payload
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _assign(target: dict[str, Any], path: str, value: Any) -> None:
    """Write into a nested dict, creating intermediate dicts along the way."""
    keys = path.split(".")
    for key in keys[:-1]:
        target = target.setdefault(key, {})
    target[keys[-1]] = value


class Adapter:
    def __init__(self, spec: dict[str, Any], source: Path | None = None) -> None:
        self.source = source
        self.vendor = Vendor(spec.get("vendor", "unknown"))
        self.integration: str = spec["integration"]
        self.matches: dict[str, str] = spec.get("matches", {})
        self.fields: dict[str, Any] = spec.get("fields", {})
        self.state_map: dict[str, str] = spec.get("state_map", {})
        self.fault_map: dict[str, str] = spec.get("fault_map", {})
        self.model: str | None = spec.get("model")
        self.capabilities = [Capability(c) for c in spec.get("capabilities", [])]

    @classmethod
    def from_file(cls, path: Path) -> Adapter:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(spec, source=path)

    def handles(self, entity: dict[str, Any]) -> bool:
        return all(_dig(entity, path) == expected for path, expected in self.matches.items())

    def _resolve(self, entity: dict[str, Any], rule: Any) -> Any:
        if isinstance(rule, str):
            return _dig(entity, rule)

        value = _dig(entity, rule["path"])
        if value is None:
            return None
        name = rule.get("transform")
        if name is None:
            return value
        if name not in TRANSFORMS:
            raise AdapterError(f"{self.source}: unknown transform {name!r}")
        return TRANSFORMS[name](value)

    def to_canonical(self, entity: dict[str, Any]) -> VacuumTelemetry:
        """Map one Home Assistant entity state payload onto the canonical model.

        ``entity`` is the HA state object: ``entity_id``, ``state``, ``attributes``.
        """
        payload: dict[str, Any] = {}
        for canonical_path, rule in self.fields.items():
            value = self._resolve(entity, rule)
            if value is not None:
                _assign(payload, canonical_path, value)

        device_payload = payload.pop("device", {})
        device = Device(
            id=device_payload.get("id") or entity["entity_id"],
            vendor=self.vendor,
            model=device_payload.get("model") or self.model,
            firmware=device_payload.get("firmware"),
            capabilities=device_payload.get("capabilities") or self.capabilities,
        )

        state_payload = payload.setdefault("state", {})
        vendor_state = entity.get("state")
        state_payload["status"] = _map_enum(self.state_map, vendor_state, Status)

        fault = self._build_fault(entity, payload.pop("fault", {}))

        return VacuumTelemetry(
            observed_at=_observed_at(entity),
            device=device,
            fault=fault,
            raw=entity,
            **payload,
        )

    def _build_fault(self, entity: dict[str, Any], mapped: dict[str, Any]) -> Fault | None:
        vendor_code = mapped.get("code_vendor")
        message = mapped.get("message")
        if vendor_code is None and message is None:
            return None
        # An explicit `null` in fault_map is how an adapter declares a healthy code.
        if self.fault_map.get(str(vendor_code), "") is None:
            return None
        return Fault(
            code_canonical=_map_enum(self.fault_map, vendor_code, FaultCode),
            code_vendor=None if vendor_code is None else str(vendor_code),
            message=message,
        )


def _map_enum[E: (Status, FaultCode)](
    mapping: dict[str, str], vendor_value: Any, enum_cls: type[E]
) -> E:
    if vendor_value is None:
        return enum_cls.UNKNOWN
    return enum_cls(mapping.get(str(vendor_value), enum_cls.UNKNOWN))


def _observed_at(entity: dict[str, Any]) -> datetime:
    stamp = entity.get("last_updated") or entity.get("last_changed")
    if stamp:
        return datetime.fromisoformat(stamp)
    return datetime.now(UTC)


class AdapterRegistry:
    def __init__(self, adapters: list[Adapter]) -> None:
        self._adapters = adapters

    @classmethod
    def from_dir(cls, directory: Path) -> AdapterRegistry:
        return cls([Adapter.from_file(p) for p in _adapter_files(directory)])

    def match(self, entity: dict[str, Any]) -> Adapter | None:
        return next((a for a in self._adapters if a.handles(entity)), None)

    def __len__(self) -> int:
        return len(self._adapters)

    def __iter__(self) -> Iterator[Adapter]:
        return iter(self._adapters)


def _adapter_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.glob("*.yaml") if not p.name.startswith("_"))
