"""Pure, dependency-free physical model and time-based signal processing.

All azimuths are clockwise from north; power is W, angles degrees, time seconds.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from math import cos, exp, expm1, isfinite, radians, sin
from typing import Protocol


@dataclass(frozen=True)
class Plane:
    """A separately metered PV plane; id is immutable across edits."""

    id: str
    name: str
    entity_id: str
    azimuth: float
    tilt: float
    peak_kw: float
    performance_factor: float = 0.85


@dataclass(frozen=True)
class SunPosition:
    """Local sun geometry and UTC observation time."""

    elevation: float
    azimuth: float
    at: datetime


def incidence(elevation: float, azimuth: float, tilt: float, facing: float) -> float:
    """Cosine of the incidence angle, clamped to the front hemisphere."""
    e, t, delta = map(radians, (elevation, tilt, azimuth - facing))
    return max(0.0, sin(e) * cos(t) + cos(e) * sin(t) * cos(delta))


class ExpectedPowerModel(Protocol):
    """Replaceable baseline. Future learned envelopes need no entity changes.

    Implementations must return finite non-negative W. Training and persistence
    belong in a separate service; this prediction path must never perform I/O.
    """

    def predict(self, plane: Plane, sun: SunPosition) -> float:
        """Return expected production at a solar position."""
        ...


class HaurwitzModel:
    """Haurwitz GHI with an explicitly approximate isotropic transposition.

    Fixed diffuse fraction 0.15 and ground albedo 0.20; this is a reference
    curve, not a calibrated irradiance measurement or PV forecast.
    """

    def predict(self, plane: Plane, sun: SunPosition) -> float:
        """Compute expected plane power without network or heavy dependencies."""
        if sun.elevation <= 0:
            return 0.0
        horizontal = sin(radians(sun.elevation))
        ghi = 1098.0 * horizontal * exp(-0.059 / horizontal)
        dhi = 0.15 * ghi
        dni = (ghi - dhi) / horizontal
        tilt_cos = cos(radians(plane.tilt))
        poa = (
            dni * incidence(sun.elevation, sun.azimuth, plane.tilt, plane.azimuth)
            + dhi * (1 + tilt_cos) / 2
            + ghi * 0.20 * (1 - tilt_cos) / 2
        )
        return plane.peak_kw * plane.performance_factor * poa


def parse_power(value: str, unit: str | None) -> float | None:
    """Accept production W/kW only; tolerate small inverter idle offsets."""
    if unit not in ("W", "kW"):
        return None
    try:
        power = float(value) * (1000 if unit == "kW" else 1)
    except TypeError, ValueError:
        return None
    if not isfinite(power) or power < -50:
        return None
    return max(0.0, power)


@dataclass
class Debounce:
    """Commit a new value only after it remains the candidate long enough."""

    value: bool | str | None = None
    candidate: bool | str | None = None
    since: float = 0

    def update(self, candidate: bool | str, now: float, delay: float) -> bool | str | None:
        """Use elapsed time, not number of source updates."""
        if candidate == self.value:
            self.candidate = None
        elif candidate != self.candidate:
            self.candidate, self.since = candidate, now
        if self.candidate is not None and now - self.since >= delay:
            self.value, self.candidate = candidate, None
        return self.value


@dataclass(frozen=True)
class Reading:
    """Independent availability of power and inferred signals."""

    actual_power: float | None
    expected_power: float
    clear_sky_ratio: float | None
    sunshine_index: float | None
    sky_condition: str | None
    direct_sun: bool | None
    reason: str


class Signal:
    """Two paths: raw ratio for fast sun, EMA plus dwell for stable sky."""

    def __init__(self) -> None:
        self.ema: float | None = None
        self.last_time: float | None = None
        self.direct = Debounce()
        self.condition = Debounce()

    def reset(self) -> None:
        """Forget stale evidence; do not restore sun-on after a restart."""
        self.__init__()

    def update(
        self,
        actual: float | None,
        expected: float,
        peak_w: float,
        sun: SunPosition,
        now: float,
        options: Mapping[str, float],
        front: bool = True,
    ) -> Reading:
        """Produce one signal; missing data never becomes a cloudy reading."""
        if sun.elevation <= 0:
            self.reset()
            return Reading(actual, expected, None, 0.0, "night", False, "night")
        if actual is None:
            self.reset()
            return Reading(None, expected, None, None, None, None, "source_unavailable")
        if sun.elevation < options["min_elevation"] or expected < max(
            20, peak_w * options["min_expected_fraction"]
        ):
            self.reset()
            return Reading(
                actual, expected, None, None, "insufficient_light", None, "insufficient_light"
            )
        ratio = actual / expected
        dt = max(0, now - self.last_time) if self.last_time is not None else 0
        tau = options["smoothing_seconds"]
        alpha = 1.0 if tau == 0 else -expm1(-dt / tau)
        bounded = min(ratio, 1.5)  # Keep brief cloud-edge spikes out of long EMA tails.
        self.ema = bounded if self.ema is None else self.ema + alpha * (bounded - self.ema)
        self.last_time = now
        threshold = options["off_ratio"] if self.direct.value is True else options["on_ratio"]
        candidate = front and ratio >= threshold
        direct = self.direct.update(
            candidate, now, options["on_delay"] if candidate else options["off_delay"]
        )
        # Geometry is conclusive: a back-facing plane cannot receive direct sun.
        if not front:
            self.direct = Debounce(value=False)
            direct = False
        old = self.condition.value
        if self.ema >= (options["off_ratio"] if old == "sunny" else options["on_ratio"]):
            sky = "sunny"
        elif self.ema < (0.45 if old == "cloudy" else 0.35):
            sky = "cloudy"
        else:
            sky = "partly_cloudy"
        condition = self.condition.update(sky, now, options["condition_delay"])
        return Reading(
            actual, expected, ratio, min(100, max(0, self.ema * 100)), condition, direct, "ok"
        )
