"""Local source tracking and clock-driven signal evaluation."""

import logging
from datetime import timedelta
from time import monotonic

import astral.sun
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.sun import get_astral_observer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DEFAULTS, DOMAIN
from .model import (
    ExpectedPowerModel,
    HaurwitzModel,
    Plane,
    Signal,
    SunPosition,
    incidence,
    parse_power,
)

_LOGGER = logging.getLogger(__name__)


class SunshineCoordinator(DataUpdateCoordinator):
    """Push source changes immediately; tick for dwell, geometry and freshness."""

    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.entry = entry
        self.planes = [Plane(**p) for p in entry.data["planes"]]
        self.options = DEFAULTS | dict(entry.options)
        self.model: ExpectedPowerModel = HaurwitzModel()
        self.signals = {p.id: Signal() for p in self.planes}
        self.signals["total"] = Signal()
        self.source_status = {}

    @callback
    def start(self):
        """Listeners are owned by the config entry and cleaned up on unload."""
        self.entry.async_on_unload(
            async_track_state_change_event(
                self.hass,
                [p.entity_id for p in self.planes]
                + [
                    self.options[k]
                    for k in ("weather_entity", "pv_inhibit_entity")
                    if self.options.get(k)
                ],
                self._changed,
            )
        )
        self.entry.async_on_unload(
            async_track_time_interval(self.hass, self._changed, timedelta(seconds=5))
        )
        self._changed()

    @callback
    def _changed(self, _event=None):
        now = dt_util.utcnow()
        observer = get_astral_observer(self.hass)
        sun = SunPosition(
            astral.sun.elevation(observer, now), astral.sun.azimuth(observer, now), now
        )
        clock = monotonic()
        readings = {}
        for plane in self.planes:
            state = self.hass.states.get(plane.entity_id)
            actual = None
            reason = "missing"
            if state is not None:
                age = (now - state.last_reported).total_seconds()
                if 0 <= age <= self.options["stale_seconds"]:
                    actual = parse_power(state.state, state.attributes.get("unit_of_measurement"))
                    reason = "ok" if actual is not None else "invalid_state_or_unit"
                else:
                    reason = "stale"
            self.source_status[plane.id] = reason
            expected = self.model.predict(plane, sun)
            readings[plane.id] = self.signals[plane.id].update(
                actual,
                expected,
                plane.peak_kw * 1000,
                sun,
                clock,
                self.options,
                incidence(sun.elevation, sun.azimuth, plane.tilt, plane.azimuth) > 0.1,
            )
        actuals = [r.actual_power for r in readings.values()]
        total_actual = sum(actuals) if all(v is not None for v in actuals) else None
        readings["total"] = self.signals["total"].update(
            total_actual,
            sum(r.expected_power for r in readings.values()),
            sum(p.peak_kw * 1000 for p in self.planes),
            sun,
            clock,
            self.options,
            any(
                incidence(sun.elevation, sun.azimuth, p.tilt, p.azimuth) > 0.1 for p in self.planes
            ),
        )
        self.async_set_updated_data({"readings": readings, "sun": sun})
