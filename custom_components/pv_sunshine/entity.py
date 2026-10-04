"""Shared entity identity and availability."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class SunshineEntity(CoordinatorEntity):
    """Stable IDs use entry and immutable plane IDs, never display names."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, scope, key, label):
        super().__init__(coordinator)
        self.scope, self.key = scope, key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{scope}_{key}"
        self._attr_name = label
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="PV Sunshine",
            model="Local PV sunshine estimator",
        )

    @property
    def reading(self):
        return self.coordinator.data["readings"][self.scope]

    @property
    def available(self):
        return super().available and getattr(self.reading, self.key) is not None

    @property
    def extra_state_attributes(self):
        return {"quality": self.reading.reason}
