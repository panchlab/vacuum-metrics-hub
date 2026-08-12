# vacuum-metrics-hub

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

## Status

v0.1: Home Assistant WebSocket source, Dreame adapter, Prometheus + InfluxDB exporters, Docker
Compose. See the [roadmap](#roadmap) below for what's next.

### Roadmap

| Version | Scope |
|---|---|
| v0.1 | HA WebSocket source, Dreame adapter, Prometheus + InfluxDB exporters, Docker Compose |
| v0.2 | Schema v1 frozen, Grafana dashboard, `_template.yaml` + CONTRIBUTING → public announcement |
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
