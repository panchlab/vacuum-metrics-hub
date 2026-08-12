import json
from pathlib import Path

import pytest
from prometheus_client import generate_latest

from vmhub.adapters.loader import AdapterRegistry
from vmhub.exporters.prometheus import PrometheusExporter

ADAPTERS = Path(__file__).parents[1] / "adapters"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def telemetry():
    entity = json.loads((FIXTURES / "dreame_x50_ultra.json").read_text(encoding="utf-8"))
    return AdapterRegistry.from_dir(ADAPTERS).match(entity).to_canonical(entity)


def samples() -> list[str]:
    """Exposition lines that carry a value, ignoring the always-present HELP/TYPE metadata."""
    return [
        line
        for line in generate_latest().decode().splitlines()
        if line and not line.startswith("#")
    ]


def test_unreported_consumables_are_absent_not_zero(telemetry) -> None:
    """Calling .labels() alone would publish a 0 series, which is a lie about the vendor."""
    PrometheusExporter().publish(telemetry)
    exposition = "\n".join(samples())

    assert 'part="main_brush"' in exposition
    assert 'part="mop_pad"' not in exposition
    assert 'part="dust_bag"' not in exposition


def test_unreported_station_counters_are_absent(telemetry) -> None:
    PrometheusExporter().publish(telemetry)

    assert not [s for s in samples() if s.startswith("vmhub_station_")]
