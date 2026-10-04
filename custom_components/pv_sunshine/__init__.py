"""PV Sunshine: local sunlight estimates from existing PV power sensors."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import PLATFORMS
from .coordinator import SunshineCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an entry without requiring the source sensors to be ready."""
    coordinator = SunshineCoordinator(hass, entry)
    entry.runtime_data = coordinator
    # Remove entities belonging to deleted planes, preserving renamed/edited ones.
    registry = er.async_get(hass)
    prefixes = tuple(
        f"{entry.entry_id}_{scope}_" for scope in ["total", *(p.id for p in coordinator.planes)]
    )
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.platform == "pv_sunshine" and not entity.unique_id.startswith(prefixes):
            registry.async_remove(entity.entity_id)
    coordinator.start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply options and plane changes atomically by reloading."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms; HA then calls registered listener cleanup functions."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
