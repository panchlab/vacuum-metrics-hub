# Metrics

## Implemented (v0.1)

### `efficiency_m2_per_min`

```
session.area_m2 / (session.duration_s / 60)
```

Baseline cleaning throughput for a single session. `null` when either input is missing — a
session with no reported area is not a session that cleaned zero square metres.

Exported as `vmhub_efficiency_m2_per_min` (Prometheus) and `efficiency_m2_per_min` (InfluxDB).

## Session records

Point-in-time samples are not enough for degradation analysis, so vmhub also emits one record per
cleaning run, written to the `vacuum_session` measurement in InfluxDB and counted as
`vmhub_sessions_total` in Prometheus.

A session is open while the status is `cleaning` or `mopping`; `paused` holds it open; anything
else closes it. A robot that recharges mid-run therefore produces two records — see
[ADR-0002](adr/0002-session-boundaries.md) for why that split is the honest one.

| Field | Meaning |
|---|---|
| `started_at` / `ended_at` | first active sample, and the sample that closed the session |
| `observed_duration_s` | wall clock measured by vmhub, bounded by HA's update cadence |
| `ended_in` | the status that closed the session — `docked`, `error`, `charging`, … |
| `area_at_start_m2` / `area_at_end_m2` | the vendor's own counter, read at both ends |
| `vendor_duration_at_start_s` / `..._at_end_s` | likewise for the vendor's cleaning time |
| `completed` | only if the vendor reports it; never inferred |

**Why two area readings.** Whether a vendor's area attribute is a per-session gauge or a lifetime
counter is not yet confirmed on real hardware. If it is a gauge, the session's area is
`area_at_end_m2`; if it is a counter, it is the difference. Storing both readings means one real
session settles the question, instead of a redesign.

## Planned (v0.4)

These need history, which is why they wait for the time-series store to accumulate sessions.

### `efficiency_drift` — the flagship metric

```
mean(efficiency over the last 30 sessions) / baseline - 1
```

where `baseline` is the mean efficiency over the first 30 sessions after the last consumable
replacement.

A sustained 15% drop means the robot is doing the same work more slowly: hair wound around the
main brush, a loaded filter, or a dirty sensor. It fires long before the vendor's own consumable
counter — which is a fixed hours-used countdown, not a measurement — reaches zero.

Dreame markets HyperStream DuoBrush as tangle-free. This metric is how you check that claim
against your own floors, and find out how many hours it holds up for.

### `consumable_burn_rate`

Linear regression over `consumables.<part>.remaining_pct` against time, extrapolated to zero.
Produces a forecast replacement date rather than "12% remaining", which tells you nothing about
whether that's a week or two months.

### `cost_per_m2`

Consumable cost over area cleaned since replacement. The real cost of ownership, per vendor.

### `mtbf_h`

Mean operating hours between `fault` events. An objective reliability comparison across brands —
the thing no review can give you, because reviewers don't run a robot for two years.

### `completion_rate`

```
count(sessions where completed) / count(sessions)
```

How often the robot gives up. Requires `session.completed`, which not every vendor reports — see
[vendor-matrix.md](vendor-matrix.md).

### `session_time_variance`

Standard deviation of duration for repeated cleans of the same room segment. Rising variance
means navigation is degrading: a dirty lidar, a moved obstacle, worsening localization.
