# Metrics

## Implemented (v0.1)

### `efficiency_m2_per_min`

```
session.area_m2 / (session.duration_s / 60)
```

Baseline cleaning throughput for a single session. `null` when either input is missing — a
session with no reported area is not a session that cleaned zero square metres.

Exported as `vmhub_efficiency_m2_per_min` (Prometheus) and `efficiency_m2_per_min` (InfluxDB).

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
