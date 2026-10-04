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
