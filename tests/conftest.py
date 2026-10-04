"""Real Home Assistant test fixtures."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pv_sunshine.const import DOMAIN

PLANE = {
    "id": "east",
    "name": "East",
    "entity_id": "sensor.pv_east",
    "azimuth": 90.0,
    "tilt": 30.0,
    "peak_kw": 5.0,
    "performance_factor": 0.85,
}


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="PV Sunshine", data={"planes": [PLANE.copy()]})
    entry.add_to_hass(hass)
    return entry
