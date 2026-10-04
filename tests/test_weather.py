"""Regional weather enrichment, actual HA entities and forecast forwarding."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.weather import WeatherEntityFeature
from homeassistant.core import SupportsResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.pv_sunshine.const import DEFAULTS, DOMAIN
from custom_components.pv_sunshine.diagnostics import async_get_config_entry_diagnostics
from custom_components.pv_sunshine.enrichment import enrich
from custom_components.pv_sunshine.model import Reading
from custom_components.pv_sunshine.weather import EnrichedWeather

from .test_form_serialization import browser_result


def reading(sky="sunny", direct=True, reason="ok"):
    return Reading(4000, 4500, 0.89, 89, sky, direct, reason)


@pytest.mark.parametrize(
    "provider,sky,direct,blocked,expected,source",
    [
        ("partlycloudy", "sunny", True, False, "sunny", "pv"),
        ("sunny", "cloudy", False, False, "cloudy", "pv"),
        ("cloudy", "partly_cloudy", False, False, "partlycloudy", "pv"),
        ("rainy", "sunny", True, False, "rainy", "weather"),
        ("snowy", "cloudy", False, False, "snowy", "weather"),
        ("fog", "sunny", True, False, "fog", "weather"),
        ("windy", "sunny", True, False, "windy", "weather"),
        ("partlycloudy", "sunny", True, True, "partlycloudy", "weather"),
        ("partlycloudy", "sunny", False, False, "partlycloudy", "weather"),
        (None, "sunny", True, False, "sunny", "pv"),
        (None, None, None, False, None, "none"),
    ],
)
def test_decisions(provider, sky, direct, blocked, expected, source):
    result = enrich(provider, reading(sky, direct), blocked)
    assert result.condition == expected
    assert result.source == source


@pytest.mark.parametrize("reason", ["night", "insufficient_light", "source_unavailable"])
def test_no_invented_night_or_low_light_weather(reason):
    assert enrich("cloudy", reading("night", False, reason), False).condition == "cloudy"
    assert enrich(None, reading("night", False, reason), False).condition is None


async def test_options_serialization_preservation_and_removal(hass, entry):
    hass.states.async_set("weather.regional", "partlycloudy")
    hass.states.async_set("binary_sensor.limited", "off")
    manager = hass.config_entries.options
    r = await manager.async_init(entry.entry_id)
    r = await manager.async_configure(r["flow_id"], {"next_step_id": "weather"})
    browser_result(manager, r)
    r = await manager.async_configure(
        r["flow_id"], {"weather_entity": "weather.missing", "weather_stale_seconds": 3600}
    )
    assert r["errors"]["base"] == "invalid_weather_source"
    r = await manager.async_configure(
        r["flow_id"],
        {
            "weather_entity": "weather.regional",
            "pv_inhibit_entity": "binary_sensor.limited",
            "weather_stale_seconds": 3600,
        },
    )
    assert entry.options["weather_entity"] == "weather.regional"
    r = await manager.async_init(entry.entry_id)
    r = await manager.async_configure(r["flow_id"], {"next_step_id": "tuning"})
    await manager.async_configure(r["flow_id"], DEFAULTS)
    assert entry.options["weather_entity"] == "weather.regional"
    r = await manager.async_init(entry.entry_id)
    r = await manager.async_configure(r["flow_id"], {"next_step_id": "weather"})
    await manager.async_configure(r["flow_id"], {"weather_stale_seconds": 3600})
    assert "weather_entity" not in entry.options
    assert "pv_inhibit_entity" not in entry.options


async def setup_weather(hass, entry):
    hass.config.latitude = 48.2
    hass.config.longitude = 16.3
    hass.config_entries.async_update_entry(
        entry,
        options=DEFAULTS
        | {
            "weather_entity": "weather.regional",
            "pv_inhibit_entity": "binary_sensor.limited",
            "weather_stale_seconds": 60,
            "on_delay": 0,
            "off_delay": 0,
            "condition_delay": 0,
        },
    )
    hass.states.async_set("binary_sensor.limited", "off")
    hass.states.async_set(
        "weather.regional",
        "partlycloudy",
        {
            "temperature": 20,
            "temperature_unit": "°C",
            "humidity": 60,
            "wind_speed": 12,
            "wind_speed_unit": "km/h",
            "cloud_coverage": 50,
            "supported_features": int(WeatherEntityFeature.FORECAST_HOURLY),
            "attribution": "Example provider",
        },
    )
    hass.states.async_set("sensor.pv_east", "5000", {"unit_of_measurement": "W"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return er.async_get(hass).async_get_entity_id(
        "weather", DOMAIN, f"{entry.entry_id}_total_enriched_weather"
    )


async def test_weather_entity_enrichment_fallback_staleness_and_cleanup(hass, entry, freezer):
    freezer.move_to("2026-06-01T10:00:00+00:00")
    entity_id = await setup_weather(hass, entry)
    state = hass.states.get(entity_id)
    assert state.state == "sunny"
    assert state.attributes["condition_source"] == "pv"
    assert state.attributes["original_condition"] == "partlycloudy"
    assert state.attributes["temperature"] == 20
    assert state.attributes["humidity"] == 60
    assert state.attributes["cloud_coverage"] == 50
    hass.states.async_set("binary_sensor.limited", "on")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "partlycloudy"
    hass.states.async_set("binary_sensor.limited", "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["enrichment_reason"] == "pv_inhibited"
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert "weather.regional" not in str(diag)
    assert "binary_sensor.limited" not in str(diag)
    hass.states.async_remove("binary_sensor.limited")
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"
    hass.states.async_set("binary_sensor.limited", "off")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "sunny"
    assert hass.states.get(entity_id).attributes.get("temperature") is None
    hass.config_entries.async_update_entry(entry, options=DEFAULTS)
    await hass.async_block_till_done()
    assert er.async_get(hass).async_get(entity_id) is None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_forecast_forwarding(hass, entry, freezer):
    freezer.move_to("2026-06-01T10:00:00+00:00")
    await setup_weather(hass, entry)
    entity = EnrichedWeather(entry.runtime_data)
    entity.hass = hass
    response = {
        "weather.regional": {
            "forecast": [
                {
                    "datetime": "2026-06-01T12:00:00+00:00",
                    "temperature": 22,
                    "condition": "rainy",
                    "precipitation": 2,
                }
            ]
        }
    }
    mock = AsyncMock(return_value=response)
    hass.services.async_register(
        "weather", "get_forecasts", mock, supports_response=SupportsResponse.ONLY
    )
    result = await entity.async_forecast_hourly()
    assert result[0]["native_temperature"] == 22
    assert result[0]["condition"] == "rainy"
    assert "temperature" in response["weather.regional"]["forecast"][0]
    assert await entity.async_forecast_daily() is None
    assert await entity.async_forecast_twice_daily() is None
    with patch.object(entity, "async_update_listeners", new_callable=AsyncMock) as refresh:
        await entity._refresh_forecast_listeners(None)
        refresh.assert_awaited_once_with(None)
    from homeassistant.exceptions import HomeAssistantError

    mock.side_effect = HomeAssistantError("provider unavailable")
    assert await entity.async_forecast_hourly() is None
    mock.side_effect = None
    mock.return_value = {}
    assert await entity.async_forecast_hourly() is None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_source_missing_units_and_loop_rejection(hass, entry, freezer):
    freezer.move_to("2026-06-01T10:00:00+00:00")
    entity_id = await setup_weather(hass, entry)
    hass.states.async_set(
        "weather.regional",
        "partlycloudy",
        {
            "temperature": 68,
            "temperature_unit": "°F",
            "wind_bearing": "NW",
            "wind_speed": 10,
            "wind_speed_unit": "mph",
            "pressure": 29.92,
            "pressure_unit": "inHg",
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["temperature"] == 20
    assert state.attributes["temperature_unit"] == "°C"
    assert state.attributes["wind_bearing"] == "NW"
    assert state.attributes["wind_speed"] == pytest.approx(16.09344, abs=0.1)
    manager = hass.config_entries.options
    result = await manager.async_init(entry.entry_id)
    result = await manager.async_configure(result["flow_id"], {"next_step_id": "weather"})
    result = await manager.async_configure(
        result["flow_id"], {"weather_entity": entity_id, "weather_stale_seconds": 3600}
    )
    assert result["errors"]["base"] == "invalid_weather_source"
    hass.states.async_remove("weather.regional")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "sunny"
    hass.states.async_set("sensor.pv_east", "unavailable", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_weather_only_source_no_inhibit_and_forecast_units(hass, entry, freezer):
    freezer.move_to("2026-06-01T10:00:00+00:00")
    hass.config_entries.async_update_entry(entry, options={"weather_entity": "weather.regional"})
    hass.states.async_set(
        "weather.regional",
        "rainy",
        {
            "temperature": 68,
            "temperature_unit": "°F",
            "supported_features": int(
                WeatherEntityFeature.FORECAST_DAILY
                | WeatherEntityFeature.FORECAST_HOURLY
                | WeatherEntityFeature.FORECAST_TWICE_DAILY
            ),
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity = EnrichedWeather(entry.runtime_data)
    entity.hass = hass
    assert entity.condition == "rainy"
    assert entity.enrichment.source == "weather"
    mock = AsyncMock(
        return_value={
            "weather.regional": {
                "forecast": [
                    {
                        "datetime": "2026-06-01T12:00:00+00:00",
                        "temperature": 77,
                        "templow": 59,
                        "condition": "partlycloudy",
                        "is_daytime": True,
                    }
                ]
            }
        }
    )
    hass.services.async_register(
        "weather", "get_forecasts", mock, supports_response=SupportsResponse.ONLY
    )
    for method in (
        entity.async_forecast_daily,
        entity.async_forecast_hourly,
        entity.async_forecast_twice_daily,
    ):
        converted = entity._convert_forecast(await method())
        assert converted[0]["temperature"] == 25
        assert converted[0]["templow"] == 15
        assert converted[0]["condition"] == "partlycloudy"
    assert await hass.config_entries.async_unload(entry.entry_id)
