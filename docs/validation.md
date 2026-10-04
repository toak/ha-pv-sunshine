# Local validation record

Validated 4 October 2026 on macOS arm64, Python 3.14.4, Home Assistant 2026.9.4 and pytest-homeassistant-custom-component 0.13.367.

- 36 tests passed using the real Home Assistant test harness.
- Combined statement/branch coverage: 99.52%; configuration flow: 100%.
- Ruff lint and formatting passed.
- Official Hassfest from Home Assistant tag 2026.9.4 passed: one integration, zero invalid integrations.
- Metadata consistency, translations and bundled PNG signature checked in tests.
- Brand icon visually inspected.

Coverage includes setup with missing inputs, W/kW conversion, non-finite/invalid/negative values, source freshness including unchanged reports, missing planes, weighted aggregation, directional geometry, hysteresis/dwell, EMA timing, cloud-edge ratios, reloads, registry cleanup, listener cleanup, configuration editing and diagnostics redaction.

GitHub Actions and the remote HACS validator must run after publication; they have not been represented as locally executed. No live inverter or field calibration has been performed. These software tests do not establish real-world sunlight-classification accuracy.
