"""Fast direct-sun estimates, including facade geometry gates."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import SunshineEntity
from .model import incidence


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = [DirectSun(coordinator, "total", "Direct sun")]
    entities.extend(
        DirectSun(coordinator, p.id, f"{p.name} direct sun") for p in coordinator.planes
    )
    entities.extend(
        DirectSun(coordinator, "total", f"Direct sun {name}", azimuth)
        for name, azimuth in (("north", 0), ("east", 90), ("south", 180), ("west", 270))
    )
    async_add_entities(entities)


class DirectSun(SunshineEntity, BinarySensorEntity):
    """Directional estimates describe unshaded vertical facades, not windows."""

    _attr_icon = "mdi:white-balance-sunny"

    def __init__(self, coordinator, scope, label, facing=None):
        super().__init__(coordinator, scope, "direct_sun", label)
        self.facing = facing
        if facing is not None:
            self._attr_unique_id += f"_{facing}"

    @property
    def is_on(self):
        if self.reading.direct_sun is None:
            return None
        sun = self.coordinator.data["sun"]
        return self.reading.direct_sun and (
            self.facing is None or incidence(sun.elevation, sun.azimuth, 90, self.facing) > 0.1
        )
