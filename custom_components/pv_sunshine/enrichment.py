"""Deterministic enrichment of regional conditions with local PV evidence."""

from dataclasses import dataclass

from .model import Reading

SKY_CONDITIONS = {"sunny", "partlycloudy", "cloudy", "clear-night"}
WEATHER_CONDITIONS = SKY_CONDITIONS | {
    "fog",
    "hail",
    "lightning",
    "lightning-rainy",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
    "windy",
    "windy-variant",
    "exceptional",
}


@dataclass(frozen=True)
class EnrichedCondition:
    """Confidence describes evidence quality, not a calibrated probability."""

    condition: str | None
    source: str
    confidence: str
    reason: str


def enrich(provider: str | None, reading: Reading, inhibited: bool) -> EnrichedCondition:
    """Refine sky conditions only; never infer absence of rain/wind from PV."""
    if provider is not None and provider not in SKY_CONDITIONS:
        return EnrichedCondition(provider, "weather", "provider_only", "non_sky_condition")
    if inhibited:
        reason = "pv_inhibited"
    elif reading.reason != "ok":
        reason = reading.reason
    elif reading.sky_condition == "sunny" and reading.direct_sun is True:
        return EnrichedCondition("sunny", "pv", "local_estimate", "local_sunshine")
    elif reading.sky_condition == "cloudy" and reading.direct_sun is False:
        return EnrichedCondition("cloudy", "pv", "local_estimate", "local_low_production")
    elif reading.sky_condition == "partly_cloudy":
        return EnrichedCondition("partlycloudy", "pv", "local_estimate", "local_variable_sunshine")
    else:
        reason = "pv_warming_up_or_transitioning"
    return EnrichedCondition(
        provider,
        "weather" if provider else "none",
        "provider_only" if provider else "unavailable",
        reason,
    )
