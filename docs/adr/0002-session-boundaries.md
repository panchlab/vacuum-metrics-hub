# ADR-0002: Session boundaries and who owns the numbers

- **Status:** Accepted
- **Date:** 2026-08-12

## Context

The metrics that justify this project — `efficiency_drift`, `consumable_burn_rate`,
`completion_rate` — all regress over *sessions*. The Home Assistant WebSocket stream provides
point-in-time state snapshots. Something has to decide where one cleaning run ends and the next
begins, and what the run's area and duration were.

Two questions had to be answered.

**Where is the boundary?** Cleaning is not one uninterrupted stretch. A run can be paused by the
user, and a robot with a large floor plan — the X50 Ultra among them — will return to the dock
to recharge and then resume. Both look identical from outside: the status leaves `cleaning`.

**Who computes area and duration?** vmhub could integrate its own samples over the session, or it
could read the counters the vendor already publishes.

## Decision

**A session is open while the status is `cleaning` or `mopping`. `paused` holds it open. Any
other status closes it.**

A mid-run recharge therefore yields two records, not one. So does an unmapped vendor status,
which is a deliberate consequence: splitting a session is a visible, correctable error, whereas
holding a session open on a status we failed to map would silently swallow the run.

**vmhub does not compute area or duration. It reads the vendor's counters at the session
boundaries.** The tracker keeps the last sample seen while the session was open, so the counters
are captured before the robot resets them.

Wall-clock duration between the first active sample and the closing one is recorded separately as
`observed_duration_s`, clearly labelled as vmhub's own observation rather than the vendor's.

## Consequences

**Good.** The boundary rule fits in one sentence and needs no timeout constant — nothing to tune,
nothing arbitrary to defend. Excluding charging time from a session is arguably more correct for
throughput: `efficiency_m2_per_min` should measure how fast the robot cleans, not how long its
battery lasts.

**Good.** Deferring to vendor counters keeps vmhub a normalization layer. A vendor that counts
area differently than we would is still self-consistent over time, which is all that drift
analysis requires — and drift is the metric that matters.

**Bad.** `completion_rate` and area-per-job are distorted for robots that recharge mid-run: one
job appears as two partial sessions. Grouping bursts back into jobs is deferred until real data
shows how often this actually happens; a `job_id` linking field was considered and rejected as
speculative, since it needs the same arbitrary timeout the boundary rule avoids.

**Bad.** Tracker state is in memory. A restart mid-clean loses that session. Persisting it means
adding a state store to the collector, which is not a trade v0.2 needs.

**Open.** Whether `session.area_m2` is a per-session gauge or a lifetime counter is not yet known
for any vendor — the reference X50 Ultra has not been observed against real data. Rather than
guess, `SessionRecord` stores the reading at both ends of the session (`area_at_start_m2`,
`area_at_end_m2`). One real session settles it, and the answer becomes a subtraction rather than
a redesign. `completed` stays `null` until a vendor reports it; inferring it from "reached the
dock" would be a guess, and this project does not publish guesses as data.
