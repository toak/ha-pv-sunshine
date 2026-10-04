# Contributing

Use Python 3.14 and a virtual environment:

```sh
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements-test.txt
ruff check .
ruff format --check .
pytest
```

Tests run the actual Home Assistant test harness, not hand-written HA mocks. Keep deterministic numerical and time-sequence tests for model changes, and flow/lifecycle tests for integration changes. No real inverter or network is needed for the test suite. CI also runs the official Hassfest and HACS validators. The pinned harness targets HA 2026.9.4; update it deliberately when adopting new HA APIs.

Keep baseline prediction in `model.py` independent of HA. No blocking I/O belongs in callbacks or predictions. Preserve unique IDs across edits; add migrations when config data changes. Do not add inverter credentials, vendor-specific dependencies or cloud calls to the local model.

For bug reports, include HA/integration versions, source units/report interval, symptoms and redacted diagnostics. Geometry and power readings can still be sensitive. Never include tokens or full HA configuration.

Before a release: run tests and both validators, review the diff, check version alignment, update CHANGELOG, and publish a tagged GitHub Release only from the tested commit. Verify the Actions results before announcing it. HACS default-list inclusion is a separate review process.
