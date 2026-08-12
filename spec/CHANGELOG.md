# Canonical schema changelog

The schema is versioned independently of the codebase, because downstream dashboards, adapters,
and consumers depend on the schema, not on vmhub's release number.

Semantics:

- **major** — a field is removed or renamed, a type changes, or an enum value changes meaning.
- **minor** — an optional field or enum value is added.
- **patch** — documentation and constraint clarifications only.

## 1.0.0 — unreleased

Initial schema. **Not yet frozen** — it stabilises in v0.2, before the public announcement.
Until then, breaking changes may land without a major bump.

- `device`: id, vendor, model, firmware, capabilities
- `state`: status, battery_pct, is_charging
- `session`: started_at, ended_at, duration_s, area_m2, segments, suction, water_flow, completed
- `consumables`: main_brush, side_brush, filter, mop_pad, sensors, dust_bag — each with
  remaining_pct, remaining_h, replaced_at
- `station`: dust_collections, mop_washes, water_tank_low, dirty_water_full
- `fault`: code_canonical, code_vendor, message
- `raw`: the untouched source payload
