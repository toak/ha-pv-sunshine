"""Check the HTTP response boundary, not only Python flow transitions."""

import json

import pytest
from homeassistant.helpers.data_entry_flow import FlowManagerIndexView

from custom_components.pv_sunshine.const import DOMAIN

from .test_config_flow import INPUT


def browser_result(manager, result):
    """Use the same serializer as HA's config-flow HTTP endpoints."""
    payload = FlowManagerIndexView(manager)._prepare_result_json(result)
    return json.loads(json.dumps(payload, allow_nan=False))


async def test_submit_name_returns_renderable_plane_form(hass):
    manager = hass.config_entries.flow
    result = await manager.async_init(DOMAIN, context={"source": "user"})
    browser_result(manager, result)
    result = await manager.async_configure(result["flow_id"], {"name": "PV Sunshine"})
    payload = browser_result(manager, result)
    assert payload["step_id"] == "plane"
    fields = {field["name"]: field for field in payload["data_schema"]}
    for key in ("azimuth", "tilt", "peak_kw", "performance_factor"):
        assert "number" in fields[key]["selector"]
    hass.states.async_set("sensor.pv_east", "100", {"unit_of_measurement": "W"})
    result = await manager.async_configure(result["flow_id"], INPUT)
    assert browser_result(manager, result)["step_id"] == "more"


@pytest.mark.parametrize("step", ["tuning", "add_plane", "edit_plane"])
async def test_options_forms_are_renderable(hass, entry, step):
    manager = hass.config_entries.options
    result = await manager.async_init(entry.entry_id)
    browser_result(manager, result)
    result = await manager.async_configure(result["flow_id"], {"next_step_id": step})
    browser_result(manager, result)
    if step == "edit_plane":
        result = await manager.async_configure(result["flow_id"], {"plane": "east"})
        assert browser_result(manager, result)["step_id"] == "update_plane"


@pytest.mark.parametrize("enable_weather", [False, True])
async def test_initial_weather_step_creates_configured_entities(hass, enable_weather):
    """Exercise setup through serialized forms and actual entry/platform creation."""
    from homeassistant import data_entry_flow
    from homeassistant.helpers import entity_registry as er

    hass.states.async_set("sensor.pv_east", "100", {"unit_of_measurement": "W"})
    hass.states.async_set(
        "weather.regional", "partlycloudy", {"temperature": 20, "temperature_unit": "°C"}
    )
    hass.states.async_set("binary_sensor.limited", "off")
    manager = hass.config_entries.flow
    result = await manager.async_init(DOMAIN, context={"source": "user"})
    result = await manager.async_configure(result["flow_id"], {"name": "PV Sunshine"})
    result = await manager.async_configure(result["flow_id"], INPUT)
    result = await manager.async_configure(result["flow_id"], {"add_another": False})
    assert browser_result(manager, result)["step_id"] == "weather"
    if enable_weather:
        result = await manager.async_configure(
            result["flow_id"], {"weather_entity": "weather.missing"}
        )
        assert result["errors"]["base"] == "invalid_weather_source"
        assert browser_result(manager, result)["step_id"] == "weather"
        options = {
            "weather_entity": "weather.regional",
            "pv_inhibit_entity": "binary_sensor.limited",
            "weather_stale_seconds": 7200,
        }
    else:
        options = {}
    result = await manager.async_configure(result["flow_id"], options)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = result["result"]
    await hass.async_block_till_done()
    weather_id = er.async_get(hass).async_get_entity_id(
        "weather", DOMAIN, f"{entry.entry_id}_total_enriched_weather"
    )
    if enable_weather:
        assert dict(entry.options) == options
        assert hass.states.get(weather_id) is not None
        assert entry.runtime_data.options["weather_entity"] == "weather.regional"
    else:
        assert "weather_entity" not in entry.options
        assert weather_id is None
    assert await hass.config_entries.async_unload(entry.entry_id)
