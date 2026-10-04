"""Privacy-conscious diagnostics: no coordinates, names or entity IDs."""

from dataclasses import asdict


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    return {
        "model": "haurwitz_isotropic_v1",
        "options": coordinator.options,
        "planes": [
            {
                "azimuth": p.azimuth,
                "tilt": p.tilt,
                "peak_kw": p.peak_kw,
                "performance_factor": p.performance_factor,
                "source_status": coordinator.source_status[p.id],
                "reading": asdict(coordinator.data["readings"][p.id]),
            }
            for p in coordinator.planes
        ],
        "total": asdict(coordinator.data["readings"]["total"]),
    }
