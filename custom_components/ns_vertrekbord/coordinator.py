"""Coordinator: fetches the departure board of one station and filters it."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NSApi, NSApiError, NSAuthError
from .const import (
    CONF_API_KEY,
    CONF_CATEGORIES,
    CONF_COUNT,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_VIA,
    DEFAULT_COUNT,
    DOMAIN,
    MAX_JOURNEYS,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
_TZ_RE = re.compile(r"([+-]\d{2})(\d{2})$")


def parse_ns_time(value: str | None) -> datetime | None:
    """NS uses '2026-11-13T22:18:00+0100'; make the offset ISO compatible."""
    if not value:
        return None
    return dt_util.parse_datetime(_TZ_RE.sub(r"\1:\2", value))


class NSCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN} {entry.title}",
                         update_interval=timedelta(seconds=UPDATE_INTERVAL))
        self.entry = entry
        self.api = NSApi(async_get_clientsession(hass), entry.data[CONF_API_KEY])
        self.station_code = entry.data[CONF_STATION_CODE]
        self.station_name = entry.data[CONF_STATION_NAME]
        self.names: dict[str, str] = {}  # UIC code -> long station name
        self._names_loaded: datetime | None = None

    @property
    def via(self) -> list[dict]:
        return list(self.entry.options.get(CONF_VIA, []))

    @property
    def categories(self) -> set[str]:
        return {c.upper() for c in self.entry.options.get(CONF_CATEGORIES, [])}

    @property
    def count(self) -> int:
        return int(self.entry.options.get(CONF_COUNT, DEFAULT_COUNT))

    async def _load_names(self) -> None:
        now = dt_util.utcnow()
        if self._names_loaded and now - self._names_loaded < timedelta(days=1):
            return
        try:
            stations = await self.api.all_stations()
            self.names = {str(s.get("UICCode")): s.get("namen", {}).get("lang") for s in stations if s.get("UICCode")}
            self._names_loaded = now
        except NSApiError as err:  # names are cosmetic, keep going
            _LOGGER.debug("Could not load station names: %s", err)

    def _matches(self, dep: dict) -> bool:
        if self.categories and str(dep.get("trainCategory") or "").upper() not in self.categories:
            return False
        if not self.via:
            return True
        codes = {str(v.get("uic")) for v in self.via if v.get("uic")}
        names = {str(v.get("name", "")).lower() for v in self.via if v.get("name")}
        for st in dep.get("routeStations") or []:
            if str(st.get("uicCode")) in codes or str(st.get("mediumName", "")).lower() in names:
                return True
            if self.names.get(str(st.get("uicCode")), "").lower() in names:
                return True
        return str(dep.get("direction", "")).lower() in names

    def _convert(self, dep: dict) -> dict:
        planned = parse_ns_time(dep.get("plannedDateTime"))
        actual = parse_ns_time(dep.get("actualDateTime")) or planned
        delay = round((actual - planned).total_seconds() / 60) if planned and actual else 0
        planned_track = dep.get("plannedTrack")
        track = dep.get("actualTrack") or planned_track
        product = dep.get("product") or {}
        return {
            "train": product.get("number"),
            "category": dep.get("trainCategory") or product.get("categoryCode"),
            "category_name": product.get("longCategoryName"),
            "operator": product.get("operatorName"),
            "direction": dep.get("direction"),
            "via": [self.names.get(str(s.get("uicCode"))) or s.get("mediumName") for s in dep.get("routeStations") or []],
            "planned": planned.isoformat() if planned else None,
            "actual": actual.isoformat() if actual else None,
            "delay_minutes": max(0, delay),
            "planned_track": planned_track,
            "track": track,
            "track_changed": bool(planned_track and track and str(track) != str(planned_track)),
            "cancelled": bool(dep.get("cancelled")),
            "messages": [m.get("message") for m in dep.get("messages") or [] if m.get("message")],
            "status": dep.get("departureStatus"),
        }

    async def _async_update_data(self) -> dict:
        await self._load_names()
        try:
            raw = await self.api.departures(self.station_code, MAX_JOURNEYS)
        except NSAuthError as err:
            raise UpdateFailed(f"NS API-sleutel geweigerd: {err}") from err
        except NSApiError as err:
            raise UpdateFailed(f"Fout bij ophalen vertrektijden: {err}") from err
        now = dt_util.utcnow()
        deps = []
        for dep in raw:
            if not self._matches(dep):
                continue
            item = self._convert(dep)
            act = dt_util.parse_datetime(item["actual"] or "")
            if act and act < now - timedelta(seconds=30):
                continue
            deps.append(item)
        return {
            "station": self.station_name,
            "station_code": self.station_code,
            "via": [v.get("name") for v in self.via],
            "fetched_at": now.isoformat(),
            "departures": deps,
            "all_routes": raw,  # used by the options flow to offer stations/categories
        }
