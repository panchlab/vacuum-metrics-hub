import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from generate_schema import SCHEMA_PATH, build  # noqa: E402


def test_committed_schema_matches_the_model() -> None:
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert committed == build(), "run scripts/generate_schema.py and commit the result"
