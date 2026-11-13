from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import NSBoardEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        DepartureInSensor(c, entry, "departure_in"),
        DepartureTimeSensor(c, entry, "departure_time"),
        DestinationSensor(c, entry, "destination"),
        TrackSensor(c, entry, "track"),
    ])


class DepartureInSensor(NSBoardEntity, SensorEntity):
    """Minutes until the next running train; carries the whole board as attributes."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:train-variant"

    @property
    def native_value(self):
        return self.minutes(self.next_running())

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        deps = self.upcoming()[: self.coordinator.count]
        first = deps[0] if deps else None
        attrs = {
            "station": data.get("station"),
            "station_code": data.get("station_code"),
            "via_filter": data.get("via"),
            "fetched_at": data.get("fetched_at"),
            "departures": [dict(d, minutes=self.minutes(d)) for d in deps],
        }
        if first:
            attrs.update({
                "category": first.get("category"),
                "category_name": first.get("category_name"),
                "direction": first.get("direction"),
                "via": first.get("via"),
                "planned_time": first.get("planned"),
                "actual_time": first.get("actual"),
                "delay_minutes": first.get("delay_minutes"),
                "planned_track": first.get("planned_track"),
                "track": first.get("track"),
                "track_changed": first.get("track_changed"),
                "cancelled": first.get("cancelled"),
                "messages": first.get("messages"),
                "train": first.get("train"),
            })
        return attrs


class DepartureTimeSensor(NSBoardEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    @property
    def native_value(self):
        dep = self.next_running()
        return dt_util.parse_datetime(dep["actual"]) if dep and dep.get("actual") else None


class DestinationSensor(NSBoardEntity, SensorEntity):
    _attr_icon = "mdi:map-marker"

    @property
    def native_value(self):
        dep = self.next_running()
        return dep.get("direction") if dep else None

    @property
    def extra_state_attributes(self):
        dep = self.next_running()
        return {"via": dep.get("via") if dep else None, "category": dep.get("category") if dep else None}


class TrackSensor(NSBoardEntity, SensorEntity):
    _attr_icon = "mdi:sign-direction"

    @property
    def native_value(self):
        dep = self.next_running()
        return dep.get("track") if dep else None

    @property
    def extra_state_attributes(self):
        dep = self.next_running()
        return {"planned_track": dep.get("planned_track") if dep else None,
                "track_changed": dep.get("track_changed") if dep else None}
