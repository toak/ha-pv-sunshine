"""Aggregate and per-plane power, ratio, index and stable sky entities."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfPower

from .const import CONDITIONS
from .entity import SunshineEntity

METRICS = {
    "actual_power": ("Actual PV power", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "expected_power": ("Expected clear-sky PV power", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "clear_sky_ratio": ("Clear-sky ratio", None, None),
    "sunshine_index": ("Sunshine index", PERCENTAGE, None),
    "sky_condition": ("Sky condition", None, SensorDeviceClass.ENUM),
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    scopes = [("total", "")] + [(p.id, f"{p.name} ") for p in coordinator.planes]
    async_add_entities(
        SunshineSensor(coordinator, scope, key, prefix + label, unit, device_class)
        for scope, prefix in scopes
        for key, (label, unit, device_class) in METRICS.items()
    )


class SunshineSensor(SunshineEntity, SensorEntity):
    """A measurement or enum; no energy/total-increasing semantics."""

    def __init__(self, coordinator, scope, key, label, unit, device_class):
        super().__init__(coordinator, scope, key, label)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if key == "sky_condition":
            self._attr_options = CONDITIONS
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 2 if key == "clear_sky_ratio" else 1

    @property
    def native_value(self):
        return getattr(self.reading, self.key)
