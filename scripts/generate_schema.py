"""Regenerate spec/vacuum-telemetry-v1.schema.json from the pydantic model.

Run after changing src/vmhub/model/canonical.py; tests/test_schema.py fails if the
committed schema has drifted from the model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vmhub.model.canonical import VacuumTelemetry

SCHEMA_PATH = Path(__file__).parents[1] / "spec" / "vacuum-telemetry-v1.schema.json"
SCHEMA_ID = (
    "https://raw.githubusercontent.com/MrVlad001/vacuum-metrics-hub"
    "/main/spec/vacuum-telemetry-v1.schema.json"
)


def build() -> dict[str, Any]:
    schema = VacuumTelemetry.model_json_schema()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        **schema,
    }


def main() -> None:
    SCHEMA_PATH.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
