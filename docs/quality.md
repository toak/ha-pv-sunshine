# Quality and release scope

This is a custom integration; it does not claim an official Home Assistant Quality Scale tier.

Implemented conventions:

- UI configuration and options, reload/unload support and config-entry-owned listeners.
- Config entry `runtime_data`, coordinator entities, stable unique IDs and one logical device per installation.
- Local calculations using current HA location without credentials or blocking I/O.
- Measurement/enum sensor semantics; explicit availability, no fabricated cloudy values on telemetry loss.
- Configuration form translations, bounds validation and ordered hysteresis thresholds.
- Independent expected-power availability; source freshness based on `last_reported`.
- Privacy-conscious diagnostics and removal of deleted planes from the entity registry.
- Reproducible real-HA lifecycle tests, numerical invariants, lint and CI validators.

Limits of verification: synthetic telemetry and real HA test harness exercise software behavior. No attached inverter or live-home field trial has been conducted. Accuracy across climates, panel technologies and curtailment regimes is not established. The physical model is an explainable heuristic and requires observation and tuning on the installation. Release 0.1.0 should be treated as an initial community release, not a certified irradiance instrument.

Publication is separate from local completion. The repository must be created using the requested `toak` account, followed by CI verification and a tagged release. Bundled brand images are included. Default HACS catalogue submission is a separate community review process.
