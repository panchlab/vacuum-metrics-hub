import json
from pathlib import Path

import pytest

from vmhub.adapters.loader import AdapterRegistry
from vmhub.analytics.kpi import efficiency_m2_per_min
from vmhub.model.canonical import FaultCode, Status, Vendor

ADAPTERS = Path(__file__).parents[1] / "adapters"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def registry() -> AdapterRegistry:
    return AdapterRegistry.from_dir(ADAPTERS)


@pytest.fixture
def dreame_entity() -> dict:
    return json.loads((FIXTURES / "dreame_x50_ultra.json").read_text(encoding="utf-8"))


def test_every_fixture_has_an_adapter(registry: AdapterRegistry) -> None:
    for fixture in FIXTURES.glob("*.json"):
        entity = json.loads(fixture.read_text(encoding="utf-8"))
        assert registry.match(entity) is not None, f"no adapter matches {fixture.name}"


def test_dreame_maps_to_canonical(registry: AdapterRegistry, dreame_entity: dict) -> None:
    telemetry = registry.match(dreame_entity).to_canonical(dreame_entity)

    assert telemetry.device.vendor is Vendor.DREAME
    assert telemetry.device.id == "vacuum.x50_ultra"
    assert telemetry.device.firmware == "3.5.9_1234"
    assert telemetry.state.status is Status.CLEANING
    assert telemetry.state.battery_pct == 87
    assert telemetry.session.area_m2 == 42.6
    assert telemetry.session.duration_s == 2280  # 38 minutes
    assert telemetry.consumables.main_brush.remaining_pct == 71
    assert telemetry.consumables.sensors.remaining_pct == 12


def test_unreported_fields_stay_none(registry: AdapterRegistry, dreame_entity: dict) -> None:
    """A field the integration does not expose must be null, never zero."""
    telemetry = registry.match(dreame_entity).to_canonical(dreame_entity)

    assert telemetry.station.mop_washes is None
    assert telemetry.station.dust_collections is None
    assert telemetry.consumables.dust_bag.remaining_pct is None
    assert telemetry.consumables.main_brush.remaining_h is None


def test_raw_payload_is_preserved(registry: AdapterRegistry, dreame_entity: dict) -> None:
    telemetry = registry.match(dreame_entity).to_canonical(dreame_entity)
    assert telemetry.raw == dreame_entity


def test_healthy_error_code_is_not_a_fault(registry: AdapterRegistry, dreame_entity: dict) -> None:
    telemetry = registry.match(dreame_entity).to_canonical(dreame_entity)
    assert telemetry.fault is None


def test_unmapped_error_code_keeps_the_vendor_value(
    registry: AdapterRegistry, dreame_entity: dict
) -> None:
    dreame_entity["attributes"]["error"] = 999
    telemetry = registry.match(dreame_entity).to_canonical(dreame_entity)

    assert telemetry.fault.code_canonical is FaultCode.UNKNOWN
    assert telemetry.fault.code_vendor == "999"


def test_mapped_error_code_is_canonicalised(registry: AdapterRegistry, dreame_entity: dict) -> None:
    dreame_entity["attributes"]["error"] = 10
    telemetry = registry.match(dreame_entity).to_canonical(dreame_entity)

    assert telemetry.fault.code_canonical is FaultCode.BIN_FULL
    assert telemetry.fault.code_vendor == "10"


def test_unknown_vendor_state_does_not_raise(
    registry: AdapterRegistry, dreame_entity: dict
) -> None:
    dreame_entity["state"] = "some_new_state_from_a_future_release"
    telemetry = registry.match(dreame_entity).to_canonical(dreame_entity)
    assert telemetry.state.status is Status.UNKNOWN


def test_efficiency(registry: AdapterRegistry, dreame_entity: dict) -> None:
    telemetry = registry.match(dreame_entity).to_canonical(dreame_entity)
    assert efficiency_m2_per_min(telemetry) == pytest.approx(42.6 / 38)


def test_efficiency_is_none_without_a_session(
    registry: AdapterRegistry, dreame_entity: dict
) -> None:
    del dreame_entity["attributes"]["cleaning_time"]
    telemetry = registry.match(dreame_entity).to_canonical(dreame_entity)
    assert efficiency_m2_per_min(telemetry) is None
