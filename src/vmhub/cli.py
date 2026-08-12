"""vmhub entry point: Home Assistant → adapters → canonical → exporters."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

from vmhub.adapters.loader import AdapterRegistry
from vmhub.exporters.influx import InfluxExporter
from vmhub.exporters.prometheus import PrometheusExporter
from vmhub.sessions import SessionTracker
from vmhub.sources.demo import DemoSource
from vmhub.sources.ha_ws import HomeAssistantWS

log = logging.getLogger("vmhub")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="vmhub")
    parser.add_argument("--adapters", type=Path, default=Path("adapters"))
    parser.add_argument("--ha-url", default=os.environ.get("HA_WS_URL"))
    parser.add_argument("--ha-token", default=os.environ.get("HA_TOKEN"))
    parser.add_argument("--prometheus-port", type=int, default=9464)
    parser.add_argument("--influx-url", default=os.environ.get("INFLUX_URL"))
    parser.add_argument("--influx-token", default=os.environ.get("INFLUX_TOKEN"))
    parser.add_argument("--influx-org", default=os.environ.get("INFLUX_ORG", "vmhub"))
    parser.add_argument("--influx-bucket", default=os.environ.get("INFLUX_BUCKET", "vacuum"))
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    parser.add_argument(
        "--demo",
        action="store_true",
        default=os.environ.get("VMHUB_DEMO") == "1",
        help="Replay simulated vacuums instead of connecting to Home Assistant. "
        "The data is invented; everything downstream of the source is the real pipeline.",
    )
    args = parser.parse_args()
    if not args.demo and (not args.ha_url or not args.ha_token):
        parser.error("HA_WS_URL and HA_TOKEN are required (or --ha-url / --ha-token, or --demo)")
    return args


async def run(args: argparse.Namespace) -> None:
    registry = AdapterRegistry.from_dir(args.adapters)
    log.info("loaded %d adapter(s) from %s", len(registry), args.adapters)

    prometheus = PrometheusExporter(args.prometheus_port)
    prometheus.start()
    log.info("prometheus exporter listening on :%d", args.prometheus_port)

    influx = (
        InfluxExporter(args.influx_url, args.influx_token, args.influx_org, args.influx_bucket)
        if args.influx_url and args.influx_token
        else None
    )

    source: DemoSource | HomeAssistantWS
    if args.demo:
        log.warning("running in demo mode - the telemetry is simulated, not from real hardware")
        source = DemoSource()
    else:
        source = HomeAssistantWS(args.ha_url, args.ha_token)

    tracker = SessionTracker()
    unmatched: set[str] = set()
    try:
        async for entity in source.stream():
            adapter = registry.match(entity)
            if adapter is None:
                if entity["entity_id"] not in unmatched:
                    unmatched.add(entity["entity_id"])
                    log.warning(
                        "no adapter for %s (platform=%s) — see CONTRIBUTING.md to add one",
                        entity["entity_id"],
                        entity.get("platform"),
                    )
                continue

            telemetry = adapter.to_canonical(entity)
            prometheus.publish(telemetry)
            if influx:
                await influx.publish(telemetry)

            session = tracker.observe(telemetry)
            if session:
                log.info(
                    "session closed: %s ran %.0fs, ended in %s",
                    session.device_id,
                    session.observed_duration_s,
                    session.ended_in.value,
                )
                prometheus.publish_session(session)
                if influx:
                    await influx.publish_session(session)
    finally:
        if influx:
            await influx.close()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
