"""Simulated source, so the stack can be demoed without a robot.

This is **not** captured data. It is a generator that emits Home Assistant-shaped payloads for
two imaginary vacuums, so `docker compose up` produces a populated dashboard on a machine with
no Home Assistant and no hardware. Everything downstream of it is the real pipeline: the real
Dreame adapter, the real session tracker, the real exporters.

The simulated clock starts a week in the past and runs fast, so a few minutes of wall time fills
a seven-day dashboard.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

SIM_STEP = timedelta(minutes=5)
"""How much simulated time passes between emitted samples."""

REAL_STEP_S = 0.02
"""Wall-clock delay per step, so the stream trickles in rather than arriving all at once."""


class DemoDevice:
    def __init__(self, entity_id: str, name: str, clean_at_hour: int, area_target: float) -> None:
        self.entity_id = entity_id
        self.name = name
        self.clean_at_hour = clean_at_hour
        self.area_target = area_target

        self.battery = 100.0
        self.area = 0.0
        self.minutes = 0
        self.error = 0
        self.consumables = {
            "main_brush_left": 92.0,
            "side_brush_left": 88.0,
            "filter_left": 80.0,
            "sensor_dirty_left": 61.0,
        }

    def _status(self, clock: datetime) -> str:
        """A single run each day, starting at the device's hour and lasting 45 minutes."""
        if clock.hour != self.clean_at_hour:
            return "docked"
        if clock.minute < 45:
            return "cleaning"
        return "returning"

    def step(self, clock: datetime, rng: random.Random) -> dict[str, Any]:
        status = self._status(clock)

        if status == "cleaning":
            if self.minutes == 0:
                self.area = 0.0
                self.error = 0
            self.minutes += int(SIM_STEP.total_seconds() // 60)
            # Throughput drifts down as the brush loads up between replacements.
            wear = 1 - (100 - self.consumables["main_brush_left"]) / 400
            self.area += self.area_target / 9 * wear * rng.uniform(0.9, 1.1)
            self.battery = max(15.0, self.battery - 1.8)
        elif status == "docked":
            if self.minutes:
                self._finish_run(rng)
            self.battery = min(100.0, self.battery + 2.5)

        return self._payload(clock, status)

    def _finish_run(self, rng: random.Random) -> None:
        self.minutes = 0
        for part, drop in (
            ("main_brush_left", 0.7),
            ("side_brush_left", 0.9),
            ("filter_left", 1.1),
            ("sensor_dirty_left", 1.6),
        ):
            self.consumables[part] = max(0.0, self.consumables[part] - drop)
        # Roughly one run in eight ends badly, so the fault panel is not permanently empty.
        self.error = rng.choice([0, 0, 0, 0, 0, 0, 0, 6, 10])

    def _payload(self, clock: datetime, status: str) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "state": status,
            "platform": "dreame_vacuum",
            "attributes": {
                "friendly_name": self.name,
                "model": "dreame.vacuum.x50ultra",
                "firmware_version": "3.5.9_1234",
                "battery_level": round(self.battery),
                "charging": status == "docked" and self.battery < 100,
                "cleaned_area": round(self.area, 1),
                "cleaning_time": self.minutes,
                "error": self.error,
                "error_description": "No error" if not self.error else "Simulated fault",
                **{k: round(v) for k, v in self.consumables.items()},
            },
            "last_updated": clock.isoformat(),
        }


class DemoSource:
    def __init__(self, days: int = 7, seed: int = 12) -> None:
        self.days = days
        self._rng = random.Random(seed)
        self._devices = [
            DemoDevice("vacuum.upstairs", "Upstairs", clean_at_hour=9, area_target=48),
            DemoDevice("vacuum.downstairs", "Downstairs", clean_at_hour=14, area_target=71),
        ]

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        clock = datetime.now().astimezone() - timedelta(days=self.days)
        end = datetime.now().astimezone()

        while True:
            for device in self._devices:
                yield device.step(clock, self._rng)
            clock += SIM_STEP
            # Once the simulated clock catches up with now, keep going in real time.
            await asyncio.sleep(REAL_STEP_S if clock < end else SIM_STEP.total_seconds())
