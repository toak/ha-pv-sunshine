# Algorithm and extension contract

## Physical baseline v1

All quantities are calculated locally. Solar position comes from `get_astral_observer(hass)` plus Astral elevation/azimuth, the same location data used by HA's Sun integration. The integration does not depend on the existence or name of `sun.sun`. Position is recomputed on updates, so a changed HA location takes effect without restart.

For sun elevation e > 0, tilt b and sun/panel azimuth difference d:

```
h = sin(e)
GHI = 1098 × h × exp(-0.059 / h)               [W/m²]
DHI = 0.15 × GHI                              [approximation]
DNI = (GHI - DHI) / h
cos(AOI) = max(0, sin(e) cos(b) + cos(e) sin(b) cos(d))
POA = DNI × cos(AOI) + DHI × (1 + cos(b))/2
      + GHI × 0.20 × (1 - cos(b))/2
expected_W = installed_kWp × performance_factor × POA
```

The final conversion follows from kWp × 1000 W/kW × POA / 1000 W/m². Below the horizon expected power is zero. The model deliberately excludes clipping: guessing a shared inverter cap would hide real loss of inferential information. The 15% diffuse fraction and 0.20 albedo are explicit simplifications, not part of the Haurwitz model itself. No seasonal correction is added to Haurwitz; the date influences solar position. High altitude, aerosol, snow reflection and unusual climates can require a different baseline.

Source powers are converted to W, checked for finite values and freshness, and summed only when **all** configured planes are valid. The aggregate ratio is sum(actual) / sum(expected), not the unweighted mean of plane ratios. Readings are asynchronous snapshots; they are not synchronized measurements.

## Signal processing

- Raw ratio = actual / expected; retained above 1 to reveal cloud-edge enhancement and model mismatch.
- EMA integrates elapsed monotonic time: `alpha = 1 - exp(-dt/tau)`. The input is capped at 1.5 to bound the recovery tail after anomalous peaks. A zero time constant disables smoothing.
- Sunshine index is `clamp(100 × EMA, 0, 100)`.
- Fast direct sun uses the **raw ratio**, >=0.75 to become on and <0.60 to become off by default. Each candidate must persist for its configured delay. The current value is unavailable at startup until one candidate is confirmed.
- Stable sky uses EMA. Sunny enters at the configured on threshold and exits below the off threshold. Cloudy enters below 0.35 and exits at 0.45. Otherwise the candidate is partly cloudy. A candidate must persist for 120 seconds by default; the previous confirmed state remains visible meanwhile.
- On/off thresholds are constrained above the cloudy band so classification is ordered.
- Cosine of incidence must exceed 0.1 for per-plane direct sun. Back-facing geometry forces off immediately, bypassing weather dwell. Directional facade sensors apply the same gate to the aggregate signal on vertical cardinal facades.
- All inference history resets on invalid daytime input, insufficient light, night, reload or restart. No sun-on state is restored from disk. A five-second timer evaluates pending candidates even when no state-changed event arrives.

Threshold decisions use sampled evidence; changes between source reports cannot be detected. Freshness measures reports to Home Assistant, not physical inverter sampling time. The model cannot infer telemetry health when an upstream service keeps re-reporting old values.

## Future self-learning envelope

`ExpectedPowerModel.predict(plane, sun) -> float` isolates the baseline from transport, entity and signal processing. `SunPosition` contains the observation time for seasonal models. `Plane.id` is stable across display-name edits. Prediction must be synchronous, side-effect-free and return finite, non-negative watts.

A later model can blend the physical baseline with a robust upper quantile (for example P95) in solar azimuth/elevation buckets. Add a separate learner and versioned HA Store persistence outside the prediction path. Required safeguards before enabling learning:

1. Minimum sample count, coverage across multiple dates and a confidence score per bucket.
2. Reject invalid, stale, curtailed and heavily clipped observations; exclude night/low-sun samples and prevent cloud-edge spikes dominating training.
3. Handle bucket wraparound, seasons, aging, replacements, source/geometry changes and retained outliers; bound storage and recorder reads.
4. Fall back to physics for sparse or stale buckets and expose baseline provenance/confidence.
5. Prevent feedback bias: a long cloudy period must not become the new clear-sky definition.
6. Add migration, reset/export and reproducibility tests before deployment.

The initial release does **not** learn, read Recorder history, store a training set or claim to discover shading automatically.
