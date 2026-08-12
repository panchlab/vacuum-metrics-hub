# Vendor matrix

Which canonical fields each vendor's Home Assistant integration actually reports. The gaps are as
important as the coverage: a blank cell means the vendor does not expose that field, and vmhub
records it as `null` rather than guessing.

Legend: ✅ reported · ⬜ not reported · ❔ untested (no fixture yet — see
[CONTRIBUTING.md](../CONTRIBUTING.md))

| Canonical field | Dreame<br>`dreame_vacuum` | Roborock | Ecovacs | iRobot |
|---|:--:|:--:|:--:|:--:|
| `state.battery_pct` | ✅ | ❔ | ❔ | ❔ |
| `state.is_charging` | ✅ | ❔ | ❔ | ❔ |
| `state.status` | ✅ | ❔ | ❔ | ❔ |
| `session.area_m2` | ✅ | ❔ | ❔ | ❔ |
| `session.duration_s` | ✅ | ❔ | ❔ | ❔ |
| `session.segments` | ⬜ | ❔ | ❔ | ❔ |
| `session.suction` | ⬜ | ❔ | ❔ | ❔ |
| `session.water_flow` | ⬜ | ❔ | ❔ | ❔ |
| `session.completed` | ⬜ | ❔ | ❔ | ❔ |
| `consumables.main_brush` | ✅ | ❔ | ❔ | ❔ |
| `consumables.side_brush` | ✅ | ❔ | ❔ | ❔ |
| `consumables.filter` | ✅ | ❔ | ❔ | ❔ |
| `consumables.sensors` | ✅ | ❔ | ❔ | ❔ |
| `consumables.mop_pad` | ⬜ | ❔ | ❔ | ❔ |
| `consumables.dust_bag` | ⬜ | ❔ | ❔ | ❔ |
| `station.dust_collections` | ⬜ | ❔ | ❔ | ❔ |
| `station.mop_washes` | ⬜ | ❔ | ❔ | ❔ |
| `fault.code_vendor` | ✅ | ❔ | ❔ | ❔ |

## Notes

**Dreame** — via the community [Tasshack/dreame-vacuum](https://github.com/Tasshack/dreame-vacuum)
HACS integration; there is no Dreame integration in the Home Assistant core. Verified against a
Dreame X50 Ultra on HA 2026.4. Consumables are reported as remaining percent only, never as
remaining hours. Session fields describe the current or most recent run, and there is no
completion flag — a run that was abandoned looks the same as one that finished, so
`completion_rate` cannot be computed for Dreame yet.

**Roborock, Ecovacs, iRobot** — no adapter yet. These columns are what the matrix is for: pick
one, follow [CONTRIBUTING.md](../CONTRIBUTING.md), and fill in a column.
