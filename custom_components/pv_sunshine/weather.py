"""Optional weather entity: regional data enriched with local sunshine."""

from datetime import timedelta
from math import isfinite

from homeassistant.components.weather import WeatherEntity, WeatherEntityFeature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .enrichment import WEATHER_CONDITIONS, enrich
from .entity import SunshineEntity

# Values in the upstream state already use the upstream entity's displayed units.
NATIVE_FIELDS = (
    "temperature",
    "apparent_temperature",
    "dew_point",
    "pressure",
    "wind_speed",
    "wind_gust_speed",
    "visibility",
)
UNIT_FIELDS = ("temperature", "pressure", "wind_speed", "visibility", "precipitation")
OTHER_FIELDS = ("humidity", "cloud_coverage", "uv_index", "wind_bearing", "ozone")
FORECAST_FLAGS = {
    "daily": WeatherEntityFeature.FORECAST_DAILY,
    "hourly": WeatherEntityFeature.FORECAST_HOURLY,
    "twice_daily": WeatherEntityFeature.FORECAST_TWICE_DAILY,
}


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.options.get("weather_entity"):
        async_add_entities([EnrichedWeather(entry.runtime_data)])


class EnrichedWeather(SunshineEntity, WeatherEntity):
    """Keep regional phenomena and forecasts; refine current sky only."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "total", "enriched_weather", "Local weather")
        self.source_entity = coordinator.options["weather_entity"]
        self._refresh_attributes()

    @property
    def source_state(self):
        state = self.coordinator.hass.states.get(self.source_entity)
        if state is None or state.state not in WEATHER_CONDITIONS:
            return None
        age = (dt_util.utcnow() - state.last_reported).total_seconds()
        if not 0 <= age <= self.coordinator.options.get("weather_stale_seconds", 3600):
            return None
        return state

    @property
    def enrichment(self):
        source = self.source_state
        inhibit_id = self.coordinator.options.get("pv_inhibit_entity")
        inhibited = False
        if inhibit_id:
            state = self.coordinator.hass.states.get(inhibit_id)
            # An unavailable configured inhibit signal cannot establish PV reliability.
            inhibited = state is None or state.state != "off"
        return enrich(source.state if source else None, self.reading, inhibited)

    @property
    def available(self):
        return self.coordinator.last_update_success and self.condition is not None

    @property
    def condition(self):
        return self.enrichment.condition

    @property
    def extra_state_attributes(self):
        result = self.enrichment
        source = self.source_state
        return {
            "condition_source": result.source,
            "sunshine_confidence": result.confidence,
            "enrichment_reason": result.reason,
            "original_condition": source.state if source else None,
            "weather_source": self.source_entity,
            "weather_source_available": source is not None,
            "local_sky_condition": self.reading.sky_condition,
        }

    def _refresh_attributes(self):
        source = self.source_state
        attrs = source.attributes if source else {}
        for key in NATIVE_FIELDS + OTHER_FIELDS:
            value = attrs.get(key)
            if key == "wind_bearing" and isinstance(value, str):
                pass
            elif not isinstance(value, int | float) or not isfinite(value):
                value = None
            setattr(self, f"_attr_{'native_' if key in NATIVE_FIELDS else ''}{key}", value)
        for key in UNIT_FIELDS:
            setattr(self, f"_attr_native_{key}_unit", attrs.get(f"{key}_unit"))
        self._attr_supported_features = WeatherEntityFeature(
            int(attrs.get("supported_features", 0)) & sum(FORECAST_FLAGS.values())
        )
        self._attr_attribution = attrs.get("attribution")

    @callback
    def _handle_coordinator_update(self):
        self._refresh_attributes()
        super()._handle_coordinator_update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._refresh_forecast_listeners, timedelta(minutes=10)
            )
        )

    async def _refresh_forecast_listeners(self, _now):
        # Only subscribed forecasts are fetched. Errors clear them, not the PV state.
        await self.async_update_listeners(None)

    async def _forecast(self, kind):
        if self.source_state is None or not self.supported_features & FORECAST_FLAGS[kind]:
            return None
        try:
            result = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self.source_entity, "type": kind},
                blocking=True,
                return_response=True,
            )
        except HomeAssistantError:
            return None
        forecasts = (result or {}).get(self.source_entity, {}).get("forecast")
        if forecasts is None:
            return None
        # HA returns displayed units; our native units match the source's display.
        native = {
            "temperature",
            "templow",
            "apparent_temperature",
            "dew_point",
            "pressure",
            "wind_speed",
            "wind_gust_speed",
            "precipitation",
        }
        return [
            {("native_" + k if k in native else k): v for k, v in row.items()} for row in forecasts
        ]

    async def async_forecast_daily(self):
        return await self._forecast("daily")

    async def async_forecast_hourly(self):
        return await self._forecast("hourly")

    async def async_forecast_twice_daily(self):
        return await self._forecast("twice_daily")
