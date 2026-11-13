"""Small client for the NS Reisinformatie API (departures and stations)."""
from __future__ import annotations

import aiohttp

from .const import API_BASE


class NSApiError(Exception):
    """Generic API error."""


class NSAuthError(NSApiError):
    """Invalid or unauthorised API key."""


class NSApi:
    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._headers = {"Ocp-Apim-Subscription-Key": api_key}

    async def _get(self, path: str, params: dict | None = None):
        try:
            async with self._session.get(
                f"{API_BASE}{path}", params=params, headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status in (401, 403):
                    raise NSAuthError(f"HTTP {resp.status}")
                if resp.status >= 400:
                    raise NSApiError(f"HTTP {resp.status}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise NSApiError(str(err)) from err

    async def search_stations(self, query: str, limit: int = 15) -> list[dict]:
        data = await self._get("/stations", {"q": query, "limit": limit})
        return [s for s in data.get("payload", []) if s.get("heeftVertrektijden", True)]

    async def all_stations(self) -> list[dict]:
        data = await self._get("/stations")
        return data.get("payload", [])

    async def departures(self, station_code: str, max_journeys: int) -> list[dict]:
        data = await self._get("/departures", {"station": station_code, "maxJourneys": max_journeys})
        return data.get("payload", {}).get("departures", [])
