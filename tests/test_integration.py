"""Real setup, entities, events, availability, diagnostics and unload."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.pv_sunshine.const import DOMAIN
from custom_components.pv_sunshine.diagnostics import async_get_config_entry_diagnostics


async def test_lifecycle(hass, entry, freezer):
    freezer.move_to("2026-06-01T10:00:00+00:00")
    hass.config.latitude = 48.2
    hass.config.longitude = 16.3
    hass.states.async_set("sensor.pv_east", "3.2", {"unit_of_measurement": "kW"})
    with patch("custom_components.pv_sunshine.coordinator.monotonic", return_value=0):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 16

    def state(key):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_total_{key}")
        return hass.states.get(entity_id)

    assert float(state("actual_power").state) == 3200
    assert float(state("expected_power").state) > 0
    assert state("sky_condition").state == "unavailable"
    hass.states.async_set("sensor.pv_east", "unavailable", {"unit_of_measurement": "kW"})
    await hass.async_block_till_done()
    assert state("actual_power").state == "unavailable"
    assert state("sunshine_index").state == "unavailable"
    assert state("expected_power").state != "unavailable"
    hass.states.async_set("sensor.pv_east", "2", {"unit_of_measurement": "kW"})
    await hass.async_block_till_done()
    assert state("actual_power").state == "2000.0"
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert "sensor.pv_east" not in str(diag)
    assert "latitude" not in str(diag) and "longitude" not in str(diag)
    freezer.tick(timedelta(seconds=301))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert state("actual_power").state == "unavailable"
    assert entry.runtime_data.source_status["east"] == "stale"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert all(
        hass.states.get(e.entity_id) is None or hass.states.get(e.entity_id).state == "unavailable"
        for e in entities
    )


async def test_start_without_source(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.data["readings"]["total"].actual_power is None
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_remove_cleans_registry_and_options_reload(hass, entry):
    from custom_components.pv_sunshine.const import DEFAULTS

    from .conftest import PLANE

    hass.config_entries.async_update_entry(
        entry,
        data={
            "planes": [PLANE, PLANE | {"id": "west", "name": "West", "entity_id": "sensor.pv_west"}]
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 22
    hass.config_entries.async_update_entry(
        entry, data={"planes": [PLANE]}, options=DEFAULTS | {"on_delay": 25}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.options["on_delay"] == 25
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 16
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_unchanged_reports_keep_source_fresh(hass, entry, freezer):
    freezer.move_to("2026-06-01T10:00:00+00:00")
    hass.states.async_set("sensor.pv_east", "100", {"unit_of_measurement": "W"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    old_changed = hass.states.get("sensor.pv_east").last_changed
    freezer.tick(timedelta(seconds=250))
    hass.states.async_set("sensor.pv_east", "100", {"unit_of_measurement": "W"})
    assert hass.states.get("sensor.pv_east").last_changed == old_changed
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert entry.runtime_data.data["readings"]["total"].actual_power == 100
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_directional_sun_and_clock_dwell(hass, entry, freezer):
    from custom_components.pv_sunshine.const import DEFAULTS

    freezer.move_to("2026-06-01T06:00:00+00:00")
    hass.config.latitude = 48.2
    hass.config.longitude = 16.3
    hass.config_entries.async_update_entry(entry, options=DEFAULTS | {"condition_delay": 10})
    hass.states.async_set("sensor.pv_east", "5000", {"unit_of_measurement": "W"})
    with patch("custom_components.pv_sunshine.coordinator.monotonic", return_value=0):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    with patch("custom_components.pv_sunshine.coordinator.monotonic", return_value=15):
        freezer.tick(timedelta(seconds=15))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
    registry = er.async_get(hass)

    def binary(suffix):
        return hass.states.get(
            registry.async_get_entity_id(
                "binary_sensor", DOMAIN, f"{entry.entry_id}_total_direct_sun{suffix}"
            )
        )

    assert binary("").state == "on"
    assert binary("_90").state == "on"
    assert binary("_270").state == "off"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_independent_plane_availability_and_weighted_ratio(hass, entry, freezer):
    from .conftest import PLANE

    freezer.move_to("2026-06-01T10:00:00+00:00")
    hass.config.latitude = 48.2
    hass.config.longitude = 16.3
    hass.config_entries.async_update_entry(
        entry,
        data={
            "planes": [
                PLANE,
                PLANE
                | {
                    "id": "west",
                    "name": "West",
                    "entity_id": "sensor.pv_west",
                    "azimuth": 270,
                    "peak_kw": 3,
                },
            ]
        },
    )
    hass.states.async_set("sensor.pv_east", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.pv_west", "200", {"unit_of_measurement": "W"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    readings = entry.runtime_data.data["readings"]
    assert readings["total"].clear_sky_ratio == 1200 / (
        readings["east"].expected_power + readings["west"].expected_power
    )
    hass.states.async_remove("sensor.pv_west")
    await hass.async_block_till_done()
    readings = entry.runtime_data.data["readings"]
    assert readings["east"].clear_sky_ratio is not None
    assert readings["west"].clear_sky_ratio is None
    assert readings["total"].clear_sky_ratio is None
    assert readings["total"].expected_power > 0
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_unload_removes_clock_and_source_listeners(hass, entry, freezer):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    with patch.object(coordinator, "async_set_updated_data") as setter:
        hass.states.async_set("sensor.pv_east", "1500", {"unit_of_measurement": "W"})
        freezer.tick(timedelta(seconds=20))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        setter.assert_not_called()
