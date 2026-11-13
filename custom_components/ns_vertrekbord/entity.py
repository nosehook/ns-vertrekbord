from __future__ import annotations

import math
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TICK_INTERVAL
from .coordinator import NSCoordinator


class NSBoardEntity(CoordinatorEntity[NSCoordinator]):
    """Base: knows the upcoming departures and counts down locally."""

    _attr_has_entity_name = True
    _attr_attribution = "Data: NS Reisinformatie API"

    def __init__(self, coordinator: NSCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="NS",
            model=f"Vertrekbord {coordinator.station_name}",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_interval(self.hass, self._tick, timedelta(seconds=TICK_INTERVAL)))

    @callback
    def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    def upcoming(self) -> list[dict]:
        now = dt_util.utcnow()
        out = []
        for dep in (self.coordinator.data or {}).get("departures") or []:
            act = dt_util.parse_datetime(dep.get("actual") or "")
            if act and act >= now - timedelta(seconds=30):
                out.append(dep)
        return out

    def first(self) -> dict | None:
        deps = self.upcoming()
        return deps[0] if deps else None

    def next_running(self) -> dict | None:
        return next((d for d in self.upcoming() if not d.get("cancelled")), None)

    @staticmethod
    def minutes(dep: dict | None) -> int | None:
        if not dep:
            return None
        act = dt_util.parse_datetime(dep.get("actual") or "")
        if not act:
            return None
        return max(0, math.floor((act - dt_util.utcnow()).total_seconds() / 60))
