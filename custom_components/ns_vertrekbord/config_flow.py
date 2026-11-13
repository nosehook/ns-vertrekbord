from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

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
)

_LOGGER = logging.getLogger(__name__)
CATEGORY_LABELS = {"SPR": "Sprinter", "IC": "Intercity", "ICD": "Intercity direct", "ICE": "ICE International",
                   "EST": "Eurostar", "NSI": "NS International", "ST": "Stoptrein", "SNT": "Sneltrein"}


def _existing_ns_key(hass) -> str | None:
    """Reuse the API key of the built-in Nederlandse Spoorwegen integration if present."""
    for entry in hass.config_entries.async_entries("nederlandse_spoorwegen"):
        key = entry.data.get("api_key")
        if key:
            return key
    for entry in hass.config_entries.async_entries(DOMAIN):
        key = entry.data.get(CONF_API_KEY)
        if key:
            return key
    return None


async def _filter_choices(api: NSApi, station_code: str) -> tuple[list[SelectOptionDict], list[SelectOptionDict]]:
    """Stations served from this station (route + destinations) and train categories."""
    deps = await api.departures(station_code, MAX_JOURNEYS)
    names: dict[str, str] = {}
    try:
        names = {str(s.get("UICCode")): s.get("namen", {}).get("lang") for s in await api.all_stations()}
    except NSApiError:
        pass
    by_name = {v.lower(): k for k, v in names.items() if v}
    stations: dict[str, str] = {}
    cats: dict[str, str] = {}
    for dep in deps:
        for st in dep.get("routeStations") or []:
            uic = str(st.get("uicCode"))
            stations[uic] = names.get(uic) or st.get("mediumName")
        direction = dep.get("direction")
        if direction:
            uic = by_name.get(direction.lower())
            stations[uic or f"name:{direction}"] = direction
        cat = dep.get("trainCategory")
        if cat:
            cats[cat] = (dep.get("product") or {}).get("longCategoryName") or CATEGORY_LABELS.get(cat, cat)
    st_opts = [SelectOptionDict(value=k, label=v) for k, v in sorted(stations.items(), key=lambda x: x[1] or "")]
    cat_opts = [SelectOptionDict(value=k, label=f"{v} ({k})") for k, v in sorted(cats.items())]
    return st_opts, cat_opts


def _filter_schema(st_opts, cat_opts, defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_VIA, default=defaults.get(CONF_VIA, [])): SelectSelector(SelectSelectorConfig(
            options=st_opts, multiple=True, custom_value=True, mode=SelectSelectorMode.DROPDOWN)),
        vol.Optional(CONF_CATEGORIES, default=defaults.get(CONF_CATEGORIES, [])): SelectSelector(SelectSelectorConfig(
            options=cat_opts, multiple=True, mode=SelectSelectorMode.LIST)),
        vol.Optional(CONF_COUNT, default=defaults.get(CONF_COUNT, DEFAULT_COUNT)): NumberSelector(NumberSelectorConfig(
            min=1, max=10, step=1, mode=NumberSelectorMode.SLIDER)),
    })


def _via_from_input(values: list[str], st_opts: list[SelectOptionDict]) -> list[dict]:
    labels = {o["value"]: o["label"] for o in st_opts}
    out = []
    for v in values or []:
        v = str(v).strip()
        if not v:
            continue
        if v.startswith("name:"):
            out.append({"uic": None, "name": v[5:]})
        elif v in labels:
            out.append({"uic": v, "name": labels[v]})
        else:  # typed by the user
            out.append({"uic": None, "name": v})
    return out


def _via_to_values(via: list[dict]) -> list[str]:
    return [v["uic"] if v.get("uic") else v.get("name") for v in via or []]


class NSVertrekbordConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._key: str | None = None
        self._stations: dict[str, str] = {}
        self._code: str | None = None
        self._name: str | None = None
        self._st_opts: list = []
        self._cat_opts: list = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NSVertrekbordOptionsFlow()

    def _api(self) -> NSApi:
        return NSApi(async_get_clientsession(self.hass), self._key)

    async def async_step_user(self, user_input=None):
        errors = {}
        existing = _existing_ns_key(self.hass)
        if user_input is not None:
            self._key = (user_input.get(CONF_API_KEY) or existing or "").strip()
            if not self._key:
                errors[CONF_API_KEY] = "no_key"
            else:
                try:
                    found = await self._api().search_stations(user_input["search"])
                except NSAuthError:
                    errors[CONF_API_KEY] = "invalid_auth"
                except NSApiError:
                    errors["base"] = "cannot_connect"
                else:
                    self._stations = {s["code"]: s.get("namen", {}).get("lang", s["code"]) for s in found if s.get("code")}
                    if self._stations:
                        return await self.async_step_station()
                    errors["search"] = "no_station"
        schema = {vol.Required("search"): str}
        if not existing:
            schema = {vol.Required(CONF_API_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)), **schema}
        return self.async_show_form(step_id="user", data_schema=vol.Schema(schema), errors=errors,
                                    description_placeholders={"key": "bestaande NS-integratie" if existing else "—"})

    async def async_step_station(self, user_input=None):
        if user_input is not None:
            self._code = user_input["station"]
            self._name = self._stations.get(self._code, self._code)
            return await self.async_step_filter()
        return self.async_show_form(step_id="station", data_schema=vol.Schema({
            vol.Required("station"): SelectSelector(SelectSelectorConfig(
                options=[SelectOptionDict(value=k, label=v) for k, v in self._stations.items()],
                mode=SelectSelectorMode.LIST)),
        }))

    async def async_step_filter(self, user_input=None):
        if not self._st_opts:
            try:
                self._st_opts, self._cat_opts = await _filter_choices(self._api(), self._code)
            except NSApiError:
                self._st_opts, self._cat_opts = [], []
        if user_input is not None:
            via = _via_from_input(user_input.get(CONF_VIA, []), self._st_opts)
            title = f"{self._name} → {', '.join(v['name'] for v in via)}" if via else self._name
            await self.async_set_unique_id(f"{self._code}|{'|'.join(sorted(v['uic'] or v['name'] for v in via))}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=title,
                data={CONF_API_KEY: self._key, CONF_STATION_CODE: self._code, CONF_STATION_NAME: self._name},
                options={CONF_VIA: via, CONF_CATEGORIES: user_input.get(CONF_CATEGORIES, []),
                         CONF_COUNT: int(user_input.get(CONF_COUNT, DEFAULT_COUNT))},
            )
        return self.async_show_form(step_id="filter", data_schema=_filter_schema(self._st_opts, self._cat_opts, {}),
                                    description_placeholders={"station": self._name})


class NSVertrekbordOptionsFlow(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._st_opts: list = []

    async def async_step_init(self, user_input=None):
        entry = self.config_entry
        api = NSApi(async_get_clientsession(self.hass), entry.data[CONF_API_KEY])
        try:
            st_opts, cat_opts = await _filter_choices(api, entry.data[CONF_STATION_CODE])
        except NSApiError:
            st_opts, cat_opts = [], []
        # keep currently selected stations selectable even if no train runs now
        known = {o["value"] for o in st_opts}
        for v in entry.options.get(CONF_VIA, []):
            val = v.get("uic") or v.get("name")
            if val not in known:
                st_opts.append(SelectOptionDict(value=val, label=v.get("name") or val))
        if user_input is not None:
            via = _via_from_input(user_input.get(CONF_VIA, []), st_opts)
            name = entry.data[CONF_STATION_NAME]
            self.hass.config_entries.async_update_entry(
                entry, title=f"{name} → {', '.join(v['name'] for v in via)}" if via else name)
            return self.async_create_entry(data={CONF_VIA: via, CONF_CATEGORIES: user_input.get(CONF_CATEGORIES, []),
                                                 CONF_COUNT: int(user_input.get(CONF_COUNT, DEFAULT_COUNT))})
        defaults = {CONF_VIA: _via_to_values(entry.options.get(CONF_VIA, [])),
                    CONF_CATEGORIES: entry.options.get(CONF_CATEGORIES, []),
                    CONF_COUNT: entry.options.get(CONF_COUNT, DEFAULT_COUNT)}
        return self.async_show_form(step_id="init", data_schema=_filter_schema(st_opts, cat_opts, defaults),
                                    description_placeholders={"station": entry.data[CONF_STATION_NAME]})
