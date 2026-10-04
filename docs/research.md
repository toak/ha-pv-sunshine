# Related work and rationale

Reviewed 4 October 2026. This is a scoped search, not proof that no equivalent project exists.

| Project | Scope | Relation to PV Sunshine |
| --- | --- | --- |
| [Forecast.Solar](https://www.home-assistant.io/integrations/forecast_solar/) | Cloud forecast of solar production | Predicts expected yield from weather; not a local fast classifier driven by actual PV power |
| [Open-Meteo Solar Forecast](https://github.com/rany2/ha-open-meteo-solar-forecast) | Weather-based PV forecast | Useful for planning; a different latency and dependency profile |
| [PV Clarity](https://github.com/stevelea/ha-pvclarity) | Forecasts, uncertainty and forecast-versus-actual calibration | Related normalization/calibration ideas, but broader forecasting purpose |
| [Smart Cover Automation](https://github.com/helgeklein/ha-smart-cover-automation) | Cover control consuming sunshine inputs, including PV-based inputs | Includes a [closely related PV template recipe](https://ha-smart-cover-automation.helgeklein.com/weather-sunny-external-pv/) with an elevation baseline, azimuth corrections, ratio and debouncing. PV Sunshine packages this general idea as a standalone integration with per-plane physical geometry, a setup UI, freshness handling and diagnostics |
| [pvlib](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.clearsky.haurwitz.html) | Scientific solar modeling, including Haurwitz and clear-sky detection | Excellent fuller modeling library; v0.1 implements a small published formula to avoid a scientific dependency stack inside HA |
| [Statistical Clear Sky Fitting](https://arxiv.org/abs/1907.08279) | Estimating clear-sky performance from historical PV data | Relevant future direction; substantially beyond a real-time first-release baseline |

The distinct target is an inverter-independent, UI-configured local HA integration producing fast and stable sunshine estimates for automation. PV Sunshine does not replace an inverter integration, energy dashboard, weather service or blind controller.

Implementation guidance: [HA config flows](https://developers.home-assistant.io/docs/core/integration/config_flow/), [HA diagnostics](https://developers.home-assistant.io/docs/core/integration-diagnostics/), [HA manifests](https://developers.home-assistant.io/docs/creating_integration_manifest/), [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/) and [HACS validation action](https://www.hacs.xyz/docs/publish/action/).
