"""Serve the bundled NS Vertrekbord Card and register it as a dashboard resource."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "ns-vertrekbord-card.js"
CARD_PATH = Path(__file__).parent / "www" / CARD_FILENAME
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"


def _resources(hass: HomeAssistant) -> tuple[Any, str | None]:
    """Return the Lovelace resource collection and resource mode.

    hass.data["lovelace"] is a LovelaceData dataclass in recent releases and a
    plain dict in older ones.
    """
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return None, None
    if isinstance(lovelace, dict):
        return lovelace.get("resources"), lovelace.get("mode")
    return getattr(lovelace, "resources", None), getattr(lovelace, "resource_mode", None)


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card file and add it to the dashboard resources."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), cache_headers=False)]
    )

    version = (await async_get_integration(hass, DOMAIN)).version
    url = f"{CARD_URL}?v={version}"

    resources, mode = _resources(hass)
    if resources is None or mode == "yaml" or not hasattr(resources, "async_create_item"):
        # YAML resource mode: resources can't be edited, load the card as an extra module.
        add_extra_js_url(hass, url)
        return

    await resources.async_get_info()  # make sure the storage collection is loaded
    ours = None
    for item in resources.async_items():
        item_url = str(item.get("url", ""))
        path = item_url.split("?", 1)[0]
        if path == CARD_URL:
            ours = item
        elif path.endswith(f"/{CARD_FILENAME}"):
            _LOGGER.warning(
                "The NS Vertrekbord Card is now included in the NS vertrekbord integration. "
                "Remove the separately installed card (dashboard resource %s) to avoid "
                "loading two versions",
                item_url,
            )

    if ours is None:
        await resources.async_create_item({"res_type": "module", "url": url})
    elif ours.get("url") != url:
        await resources.async_update_item(ours["id"], {"res_type": "module", "url": url})


async def async_unregister_card(hass: HomeAssistant) -> None:
    """Remove the card from the dashboard resources."""
    resources, mode = _resources(hass)
    if resources is None or mode == "yaml" or not hasattr(resources, "async_delete_item"):
        return
    await resources.async_get_info()
    for item in list(resources.async_items()):
        if str(item.get("url", "")).split("?", 1)[0] == CARD_URL:
            await resources.async_delete_item(item["id"])
