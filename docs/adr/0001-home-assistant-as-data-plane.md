# ADR-0001: Home Assistant as the universal data plane

- **Status:** Accepted
- **Date:** 2026-08-12

## Context

The project needs vacuum telemetry from multiple vendors. There are three ways to get it.

**Talk to vendor protocols directly.** Dreame — the reference device for this project, an X50
Ultra — publishes no open API and no protocol documentation. Its app talks to a cloud service
authenticated with a Dreamehome or Xiaomi account. Reverse-engineering that is months of work
for one vendor, has to be redone for every other vendor, breaks on firmware and API changes, and
sits in murky territory with respect to the vendor's terms of service.

**Run fully local firmware.** Valetudo replaces the vendor cloud entirely, which is the
technically superior answer where it works. It does not work well on recent Dreame models, and
the X50 is not supported. Building on it would restrict the project to a small slice of hardware.

**Consume Home Assistant.** HA already has integrations for the major vendors — for Dreame, the
[Tasshack/dreame-vacuum](https://github.com/Tasshack/dreame-vacuum) HACS integration, which is a
full app replacement including maps. HA exposes every integration's entities through one
WebSocket API with a uniform state/attributes shape.

Note that no official Dreame integration exists in the HA core; several blog posts claim
otherwise and are wrong. The HACS component is community-maintained.

## Decision

Home Assistant is the data plane. vmhub connects to HA's WebSocket API, reads `vacuum.*` entity
states, and builds its value in the layer above: canonical schema, declarative adapters, and
degradation analytics.

vmhub does not implement any vendor protocol.

## Consequences

**Good.** Every vendor HA supports, vmhub supports for the cost of one YAML file. Vendor protocol
churn is absorbed by the integration maintainers, who are far better placed to handle it. The
project's scope stays on the part nobody else is doing — normalization and analytics.

**Bad.** vmhub inherits HA's dependency chain. For Dreame that means a cloud round-trip, an
internet requirement, and command latency around two seconds. If Dreame changes its cloud auth,
everything below it stops until the HACS integration catches up. vmhub cannot honestly advertise
local control for such devices, and the README says so explicitly.

**Also bad.** HACS integrations rename attributes between releases with no deprecation cycle.
Mitigated by keeping a real state dump per device in `tests/fixtures/` and running the adapters
against them in CI, so a rename surfaces as a failing test rather than a silently null metric.
