"""Drive actual HA flow managers."""

from homeassistant import data_entry_flow

from custom_components.pv_sunshine.const import DEFAULTS, DOMAIN

from .conftest import PLANE

INPUT = {k: v for k, v in PLANE.items() if k != "id"}


async def test_setup_multiple_and_duplicate(hass):
    hass.states.async_set("sensor.pv_east", "1200", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.pv_west", "1", {"unit_of_measurement": "kW"})
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert r["step_id"] == "user"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"name": "PV Sunshine"})
    assert r["step_id"] == "plane"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], INPUT)
    assert r["step_id"] == "more"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"add_another": True})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], INPUT)
    assert r["errors"]["base"] == "duplicate_source"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], INPUT | {"name": "West", "entity_id": "sensor.pv_west", "azimuth": 270}
    )
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"add_another": False})
    assert r["step_id"] == "weather"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
    assert r["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert len(r["data"]["planes"]) == 2
    assert r["data"]["planes"][0]["id"] != r["data"]["planes"][1]["id"]
    await hass.async_block_till_done()


async def test_invalid_source(hass):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"name": "PV"})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], INPUT)
    assert r["errors"]["base"] == "invalid_source"


async def test_tuning(hass, entry):
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "tuning"})
    assert r["step_id"] == "tuning"
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], DEFAULTS | {"off_ratio": 0.8}
    )
    assert r["errors"]["base"] == "threshold_order"
    r = await hass.config_entries.options.async_configure(r["flow_id"], DEFAULTS | {"on_delay": 20})
    assert r["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options["on_delay"] == 20


async def test_edit_preserves_id(hass, entry):
    hass.states.async_set("sensor.new", "123", {"unit_of_measurement": "W"})
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"next_step_id": "edit_plane"}
    )
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"plane": "east"})
    assert r["step_id"] == "update_plane"
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], INPUT | {"entity_id": "sensor.new", "tilt": 12}
    )
    assert r["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.data["planes"][0]["id"] == "east"
    assert entry.data["planes"][0]["tilt"] == 12


async def test_last_plane_cannot_be_removed(hass, entry):
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"next_step_id": "remove_plane"}
    )
    assert r["reason"] == "last_plane"


async def test_add_remove_and_validation(hass, entry):
    hass.states.async_set("sensor.pv_west", "1", {"unit_of_measurement": "kW"})
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"next_step_id": "add_plane"}
    )
    r = await hass.config_entries.options.async_configure(r["flow_id"], INPUT)
    assert r["errors"]["base"] == "duplicate_source"
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], INPUT | {"name": "West", "entity_id": "sensor.pv_west"}
    )
    assert r["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert len(entry.data["planes"]) == 2
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"next_step_id": "edit_plane"}
    )
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"plane": "east"})
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], INPUT | {"entity_id": "sensor.pv_west"}
    )
    assert r["errors"]["base"] == "duplicate_source"
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"next_step_id": "remove_plane"}
    )
    assert r["step_id"] == "remove_plane"
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"plane": "east"})
    assert r["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert len(entry.data["planes"]) == 1


def test_reject_invalid_numbers():
    import pytest
    import voluptuous as vol

    from custom_components.pv_sunshine.config_flow import plane_schema

    for field, value in [
        ("tilt", 91),
        ("peak_kw", 0),
        ("azimuth", -1),
        ("azimuth", 360),
        ("peak_kw", float("nan")),
        ("tilt", float("inf")),
    ]:
        with pytest.raises(vol.Invalid):
            plane_schema()(INPUT | {field: value})


async def test_cannot_feed_own_output_back_into_model(hass, entry):
    from homeassistant.helpers import entity_registry as er

    from custom_components.pv_sunshine.config_flow import source_error

    registry = er.async_get(hass)
    source = registry.async_get_or_create("sensor", DOMAIN, "own_output", config_entry=entry)
    hass.states.async_set(source.entity_id, "2000", {"unit_of_measurement": "W"})
    assert source_error(hass, [], INPUT | {"entity_id": source.entity_id}) == "invalid_source"
