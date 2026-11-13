from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import NSBoardEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DelayedSensor(c, entry, "delayed"), CancelledSensor(c, entry, "cancelled")])


class DelayedSensor(NSBoardEntity, BinarySensorEntity):
    """Next running train is delayed."""

    _attr_icon = "mdi:train-car-passenger-variant"

    @property
    def is_on(self):
        dep = self.next_running()
        return bool(dep and (dep.get("delay_minutes") or 0) > 0) if dep else None

    @property
    def extra_state_attributes(self):
        dep = self.next_running()
        return {"delay_minutes": dep.get("delay_minutes") if dep else None}


class CancelledSensor(NSBoardEntity, BinarySensorEntity):
    """The first upcoming train on the board does not run."""

    _attr_icon = "mdi:train-variant"

    @property
    def is_on(self):
        dep = self.first()
        return bool(dep and dep.get("cancelled")) if dep else None
