"""Physical invariants and adversarial signal sequences."""

from datetime import UTC, datetime
from math import exp

import pytest

from custom_components.pv_sunshine.const import DEFAULTS
from custom_components.pv_sunshine.model import (
    HaurwitzModel,
    Plane,
    Signal,
    SunPosition,
    incidence,
    parse_power,
)

SUN = SunPosition(40, 90, datetime(2026, 6, 1, tzinfo=UTC))
PLANE = Plane("east", "East", "sensor.east", 90, 30, 5)


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        ("1.2", "kW", 1200),
        ("12", "W", 12),
        ("-10", "W", 0),
        ("-0.05", "kW", 0),
        ("-51", "W", None),
        ("nan", "W", None),
        ("inf", "W", None),
        ("unavailable", "W", None),
        ("unknown", "W", None),
        ("12", "kWh", None),
        ("12", None, None),
        ("12", "MW", None),
    ],
)
def test_power(value, unit, expected):
    assert parse_power(value, unit) == expected


def test_physics():
    model = HaurwitzModel()
    east = model.predict(PLANE, SUN)
    west = model.predict(Plane("west", "West", "sensor.west", 270, 30, 5), SUN)
    assert 3000 < east < 5000
    assert east > west
    assert model.predict(PLANE, SunPosition(-1, 90, SUN.at)) == 0
    horizontal = Plane("h", "H", "sensor.h", 0, 0, 1, 1)
    assert model.predict(horizontal, SunPosition(90, 180, SUN.at)) == pytest.approx(1035.0920325)
    assert incidence(30, 90, 90, 270) == 0
    assert incidence(30, 0, 90, 0) == pytest.approx(incidence(30, 180, 90, 180))


def update(signal, ratio, now, **kwargs):
    return signal.update(
        ratio * 4000 if ratio is not None else None, 4000, 5000, SUN, now, DEFAULTS, **kwargs
    )


def test_fast_hysteresis_and_dwell():
    s = Signal()
    for ratio, time, result in [
        (0.9, 0, None),
        (0.9, 9, None),
        (0.9, 10, True),
        (0.65, 50, True),
        (0.2, 60, True),
        (0.2, 89, True),
        (0.2, 90, False),
        (0.65, 110, False),
        (0.9, 120, False),
        (0.9, 130, True),
    ]:
        assert update(s, ratio, time).direct_sun is result


def test_short_cloud_cancels_off_timer():
    s = Signal()
    update(s, 1, 0)
    update(s, 1, 10)
    update(s, 0.1, 20)
    assert update(s, 1, 40).direct_sun is True
    assert update(s, 0.1, 60).direct_sun is True
    assert update(s, 0.1, 89).direct_sun is True


def test_missing_resets_all_evidence():
    s = Signal()
    update(s, 1, 0)
    update(s, 1, 120)
    assert update(s, None, 121).direct_sun is None
    assert update(s, 1, 122).direct_sun is None
    assert update(s, 1, 132).direct_sun is True
    assert update(s, 1, 132).sky_condition is None


def test_stable_sky_and_time_based_smoothing():
    s = Signal()
    update(s, 1, 0)
    assert update(s, 1, 120).sky_condition == "sunny"
    assert update(s, 0, 121).sky_condition == "sunny"
    r = update(s, 0, 181)
    assert r.sunshine_index == pytest.approx(100 * exp(-61 / 60))
    update(s, 0, 300)
    assert update(s, 0, 420).sky_condition == "cloudy"


def test_night_low_light_and_geometry():
    s = Signal()
    night = SunPosition(-10, 0, SUN.at)
    r = s.update(None, 0, 5000, night, 0, DEFAULTS)
    assert r.sky_condition == "night" and r.direct_sun is False
    assert r.clear_sky_ratio is None and r.actual_power is None
    r = s.update(10, 30, 5000, SUN, 1, DEFAULTS)
    assert r.sky_condition == "insufficient_light" and r.direct_sun is None
    assert update(s, 1, 10, front=False).direct_sun is False


def test_ratio_not_clamped_but_index_is():
    r = update(Signal(), 1.8, 0)
    assert r.clear_sky_ratio == 1.8 and r.sunshine_index == 100


def test_fixed_geometry_scaling():
    model = HaurwitzModel()
    for elevation in (0.1, 1, 5, 30, 60, 90):
        for azimuth in range(0, 360, 15):
            sun = SunPosition(elevation, azimuth, SUN.at)
            for tilt in (0, 30, 90):
                p = Plane("p", "P", "sensor.p", 90, tilt, 2, 0.8)
                q = Plane("q", "Q", "sensor.q", 90, tilt, 4, 0.8)
                assert model.predict(p, sun) >= 0
                assert model.predict(q, sun) == pytest.approx(2 * model.predict(p, sun))
