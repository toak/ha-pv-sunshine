"""Constants for PV Sunshine."""

from homeassistant.const import Platform

DOMAIN = "pv_sunshine"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.WEATHER]
DEFAULTS = {
    "smoothing_seconds": 60.0,
    "on_ratio": 0.75,
    "off_ratio": 0.60,
    "on_delay": 10.0,
    "off_delay": 30.0,
    "condition_delay": 120.0,
    "stale_seconds": 300.0,
    "min_elevation": 5.0,
    "min_expected_fraction": 0.03,
}
CONDITIONS = ["sunny", "partly_cloudy", "cloudy", "night", "insufficient_light"]
