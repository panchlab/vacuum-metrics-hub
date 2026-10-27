# vacuum-metrics-hub

[![ci](https://github.com/panchlab/vacuum-metrics-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/panchlab/vacuum-metrics-hub/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

Vendor-agnostic telemetry and predictive maintenance for robot vacuums, built on top of
[Home Assistant](https://www.home-assistant.io/).

Every vacuum vendor names the same thing differently — Dreame's `cleaned_area`, Roborock's
`total_cleaned_area`, Ecovacs' and iRobot's own conventions. A dashboard spanning vacuums from
three different brands is, today, a pile of hand-written template sensors. vacuum-metrics-hub
normalizes vendor telemetry into one canonical schema and layers predictive-maintenance
analytics on top — the kind of insight ("your main brush is degrading") that no single vendor
app gives you, because none of them compare against your own robot's history.

## Why Home Assistant as the data plane

Most vacuum vendors, including Dreame, don't publish an open API or protocol. Reverse-engineering
one is months of work and a ToS risk. Home Assistant already has community integrations for the
major vendors and normalizes the transport problem for us — so vmhub treats HA as a universal
data plane and builds its own value one layer above it. See
[docs/adr/0001-home-assistant-as-data-plane.md](docs/adr/0001-home-assistant-as-data-plane.md)
for the full reasoning.

## Architecture

```
Dreame / Roborock / Ecovacs / Roomba
              │  (HACS / core integrations)
              ▼
      Home Assistant  ──── WebSocket API (state_changed events)
              │
              ▼
   ┌─────────────────────────────┐
   │  vacuum-metrics-hub         │
   │  ┌────────────────────────┐ │
   │  │ Adapters (YAML)        │ │   vendor attributes → canonical model
   │  │ vendor → canonical     │ │
   │  └───────────┬────────────┘ │
   │  ┌───────────▼────────────┐ │
   │  │ Canonical model v1     │ │
   │  └───────────┬────────────┘ │
   │  ┌───────────▼────────────┐ │
   │  │ Session tracker        │ │   samples → one record per cleaning run
   │  └───────────┬────────────┘ │
   │  ┌───────────▼────────────┐ │
   │  │ Analytics engine       │ │   KPI / forecast / anomaly detection
   │  └───────────┬────────────┘ │
   └──────────────┼──────────────┘
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   Prometheus   InfluxDB      MQTT → back into HA (v0.3)
        │            │
        └─────┬──────┘
              ▼
           Grafana
```

## Canonical schema

Every vendor is mapped onto one schema (`spec/vacuum-telemetry-v1.schema.json`,
implemented as pydantic models in [`src/vmhub/model/canonical.py`](src/vmhub/model/canonical.py)):
`device`, `state`, `session`, `consumables`, `station`, `fault`.

Two rules the schema never breaks:

1. **Raw data is never discarded.** `code_vendor` and the full raw HA attribute payload are kept
   alongside the normalized fields.
2. **A missing field is not zero.** If a vendor doesn't expose `mop_washes`, it's `null`, not `0`
   — otherwise the analytics quietly lie.

## Adapters are declarative

Adapters live in [`adapters/*.yaml`](adapters/) — plain YAML field mappings, not Python. Anyone
can add support for their vacuum by copying [`adapters/_template.yaml`](adapters/_template.yaml)
and opening a PR. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/vendor-matrix.md](docs/vendor-matrix.md) for the current coverage per vendor.

## Sessions

Degradation analysis regresses over cleaning runs, not over samples, so vmhub tracks session
boundaries and emits one record per run. The rule is one sentence: a session is open while the
robot is `cleaning` or `mopping`, `paused` holds it open, anything else closes it.

vmhub does not recompute area or duration — the vendor already reports both, and this is a
normalization layer, not a reimplementation of the robot. What the tracker contributes is the
*moment* to read those counters, before the robot resets them.
[ADR-0002](docs/adr/0002-session-boundaries.md) covers the trade-offs, including what a mid-run
recharge does to the record.

## Analytics

| Metric | What it computes | Why it matters |
|---|---|---|
| `efficiency_m2_per_min` | area / duration | baseline cleaning throughput |
| `efficiency_drift` | rolling window vs. baseline | a 15% drop means a tangled brush or clogged filter, long before the vendor app admits it |
| `consumable_burn_rate` | linear regression on `remaining_pct` | a forecast replacement date, not just "12% left" |
| `completion_rate` | completed / total sessions | how often the robot gives up |

See [docs/metrics.md](docs/metrics.md) for the full list and formulas.

## Quick start

```bash
cp .env.example .env   # set HA_TOKEN (a Home Assistant long-lived access token) and HA_WS_URL
docker compose up -d
```

This starts `vmhub` (HA WebSocket source → adapters → Prometheus + InfluxDB exporters),
Prometheus, InfluxDB, and a provisioned Grafana instance at `localhost:3000`.

### Try it without a vacuum

```bash
VMHUB_DEMO=1 docker compose up -d
```

Demo mode replaces the Home Assistant source with a generator that simulates two vacuums over a
week, so the dashboard fills in within a few minutes on a machine with no Home Assistant and no
hardware. **The telemetry is invented** — but everything downstream of the source is the real
pipeline: the real adapter, the real session tracker, the real exporters. It is there so you can
see the shape of the thing before wiring up your own robot.

It also earns its keep as a test: it was demo mode that caught the exporter publishing `0` for
consumables the vendor never reports.

## Status

**Not yet validated against real hardware.** The pipeline runs and the test suite is green, but
it has never been pointed at a live Home Assistant instance. The Dreame adapter's attribute names
come from documentation rather than observation, and `tests/fixtures/dreame_x50_ultra.json` is a
hand-written sample, not a capture. Until a real dump replaces it, treat the Dreame column of the
[vendor matrix](docs/vendor-matrix.md) as unverified.

### Roadmap

| Version | Scope |
|---|---|
| v0.1 | HA WebSocket source, Dreame adapter, Prometheus + InfluxDB exporters, Docker Compose |
| v0.2 | Session tracking, schema v1 frozen, Grafana dashboard, `_template.yaml` + CONTRIBUTING → public announcement |
| v0.3 | MQTT Discovery back into HA, community-contributed Roborock / Ecovacs adapters |
| v0.4 | `efficiency_drift`, forecasting, anomaly detection + one-click HA add-on |
| v1.0 | Stable API, schema documented as a standalone standard |

## Risks

- **Cloud dependency.** Dreame (and most vendors) require their cloud API — a rebrand or auth
  change upstream breaks the chain below it. Mitigated by depending on HA's abstraction rather
  than any vendor protocol directly.
- **Attribute drift.** HACS integrations change attribute names between releases. Mitigated by
  the fixture-based regression tests in `tests/fixtures/`.
- This project does not offer local-only control for vendors (like Dreame) that don't support it
  — that would be a false promise.

## License

Apache-2.0 — see [LICENSE](LICENSE).
