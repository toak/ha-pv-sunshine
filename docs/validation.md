# Local validation record

Validated 4 October 2026 on macOS arm64, Python 3.14.4, Home Assistant 2026.9.4 and pytest-homeassistant-custom-component 0.13.367.

- 36 tests passed using the real Home Assistant test harness.
- Combined statement/branch coverage: 99.52%; configuration flow: 100%.
- Ruff lint and formatting passed.
- Official Hassfest from Home Assistant tag 2026.9.4 passed: one integration, zero invalid integrations.
- Metadata consistency, translations and bundled PNG signature checked in tests.
- Brand icon visually inspected.

Coverage includes setup with missing inputs, W/kW conversion, non-finite/invalid/negative values, source freshness including unchanged reports, missing planes, weighted aggregation, directional geometry, hysteresis/dwell, EMA timing, cloud-edge ratios, reloads, registry cleanup, listener cleanup, configuration editing and diagnostics redaction.

The initial [GitHub Validate run](https://github.com/toak/ha-pv-sunshine/actions/runs/37181290133) also passed all three jobs on Linux: tests, official Hassfest and HACS. Later commits and the release tag retain the same required checks. No live inverter or field calibration has been performed. These software tests do not establish real-world sunlight-classification accuracy.

## 0.1.1 setup regression

The initial tests missed HA's HTTP form serialization boundary. Reproduced the first-submit failure with the actual `FlowManagerIndexView` serializer: four new tests failed on 0.1.0 (initial plane, tuning, add-plane and edit-plane forms). After replacing opaque numeric validators with native number selectors, all 40 tests pass, including JSON serialization of those forms and the existing finite/range validation. Coverage remains 99.52%. Local lint, formatting and official Hassfest pass.

## 0.2.0 weather enrichment

59 tests pass against HA 2026.9.4; combined statement/branch coverage is 99.66%. The weather module and enrichment policy have 100% coverage. Cases include sunny/cloudy refinement, preserved rain/snow/fog/wind, warm-up and nighttime fallback, stale/missing sources, optional inhibition, feedback-loop rejection, option persistence/removal, privacy redaction, source unit conversion and all three forecast types. Ruff and local official Hassfest pass. Tests use synthetic HA states and mocked provider forecast responses; no live-provider accuracy or real-home field trial is claimed.
