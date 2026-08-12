# Contributing

The most valuable contribution to this project is **an adapter for a vacuum we don't support
yet**. It's a YAML file. You do not need to write or read any Python.

## Adding your vacuum

### 1. Find out what your integration exposes

In Home Assistant, open **Developer Tools → States**, find your `vacuum.*` entity, and copy the
full attribute block. That block is the entire input to an adapter.

While you're there, note the *integration* name — **Settings → Devices & Services**, click your
vacuum's integration; the name in the URL (e.g. `roborock`) is what goes in `matches.platform`.

### 2. Write the adapter

```bash
cp adapters/_template.yaml adapters/<integration>.yaml
```

Map the vendor attributes you found onto the canonical field paths. The canonical fields are
listed in [`spec/vacuum-telemetry-v1.schema.json`](spec/vacuum-telemetry-v1.schema.json) and
documented in [`docs/metrics.md`](docs/metrics.md).

**Map only what your integration actually reports.** If it has no `mop_washes`, leave the line
out — the field stays `null`. Do not map it to something approximate, and never substitute `0`.
A null means "unknown", and the analytics engine treats it as such; a zero would be silently
averaged into every fleet metric.

### 3. Add a fixture

Save the attribute block from step 1 as `tests/fixtures/<vendor>_<model>.json`, wrapped in the
Home Assistant state shape:

```json
{
  "entity_id": "vacuum.your_robot",
  "state": "cleaning",
  "platform": "your_integration",
  "attributes": { "...": "paste here" },
  "last_updated": "2026-08-12T09:41:37.882000+00:00"
}
```

Scrub anything personal first — room names, tokens, coordinates, MAC addresses.

This fixture is what lets CI keep your vacuum working. The maintainers own one Dreame X50 Ultra;
every other device stays supported only because its fixture is in the test suite.

### 4. Update the matrix

Add a row to [`docs/vendor-matrix.md`](docs/vendor-matrix.md) showing which canonical fields your
vendor covers, including the gaps. The gaps are the honest, useful part of that table.

### 5. Run the checks

```bash
pip install -e ".[dev]" && ruff check . && mypy && pytest
```

Then open a PR. `tests/test_adapters.py::test_every_fixture_has_an_adapter` will confirm your
adapter matches your fixture.

## Changing the canonical schema

The schema is versioned independently of the code — see
[`spec/CHANGELOG.md`](spec/CHANGELOG.md). Adding an optional field is a minor bump. Renaming or
removing a field, or changing an enum's meaning, is a major bump and needs a strong case, since
every downstream dashboard and adapter depends on it.

After editing `src/vmhub/model/canonical.py`:

```bash
python scripts/generate_schema.py
```

and commit the regenerated schema. `tests/test_schema.py` fails if you forget.

## Changing Python code

Keep changes small and scoped. `ruff check`, `ruff format`, `mypy` (strict), and `pytest` all run
in CI and all must pass.
