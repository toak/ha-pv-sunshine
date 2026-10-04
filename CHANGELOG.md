# Changelog

## 0.1.1

- Fix the unknown error after submitting the installation name: numeric fields now use serializable Home Assistant number selectors.
- Fix the same serialization error in plane editing and detection settings.
- Preserve finite-number and range validation, and add regression tests using HA’s HTTP form serializer.

## 0.1.0

Initial community release:

- Multiple independently metered PV planes with setup and options flows.
- Fully local Haurwitz reference, plane transposition and adjustable performance factor.
- Aggregate/per-plane power, ratio, index, stable conditions and fast direct-sun estimates.
- Cardinal facade estimates, time-based smoothing, hysteresis and dwell timers.
- Explicit night/low-light/invalid-source handling and freshness checks.
- Redacted diagnostics, registry cleanup, tests and validation workflows.
- Replaceable baseline interface for future learned envelopes.

No field calibration or live-home validation is claimed for this initial version.
