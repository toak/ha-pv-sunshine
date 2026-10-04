"""UI setup and editing for independently metered PV planes."""

from copy import deepcopy
from math import isfinite
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import DEFAULTS, DOMAIN


class FiniteNumberSelector(selector.NumberSelector):
    """A native, serializable number control that also rejects NaN."""

    def __call__(self, data):
        value = super().__call__(data)
        if not isfinite(value):
            raise vol.Invalid("value must be finite")
        return value


def number(low, high):
    """Use HA's number selector so forms serialize for the frontend."""
    return FiniteNumberSelector(
        selector.NumberSelectorConfig(
            min=low, max=high, step="any", mode=selector.NumberSelectorMode.BOX
        )
    )


def plane_schema(defaults=None):
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required("name", default=defaults.get("name", "PV plane")): vol.All(
                str, vol.Length(min=1, max=80)
            ),
            vol.Required(
                "entity_id", default=defaults.get("entity_id", vol.UNDEFINED)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required("azimuth", default=defaults.get("azimuth", 180)): number(0, 359.999),
            vol.Required("tilt", default=defaults.get("tilt", 30)): number(0, 90),
            vol.Required("peak_kw", default=defaults.get("peak_kw", 5)): number(0.01, 10000),
            vol.Required(
                "performance_factor", default=defaults.get("performance_factor", 0.85)
            ): number(0.1, 1.5),
        }
    )


def source_error(hass, planes, data, editing=None):
    if any(p["entity_id"] == data["entity_id"] and p["id"] != editing for p in planes):
        return "duplicate_source"
    registered = er.async_get(hass).async_get(data["entity_id"])
    if registered is not None and registered.platform == DOMAIN:
        return "invalid_source"
    state = hass.states.get(data["entity_id"])
    if state is None or state.attributes.get("unit_of_measurement") not in ("W", "kW"):
        return "invalid_source"
    return None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create one logical installation containing any number of planes."""

    VERSION = 1

    def __init__(self):
        self.planes = []
        self.title = "PV Sunshine"

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.title = user_input["name"]
            return await self.async_step_plane()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("name", default=self.title): vol.All(str, vol.Length(min=1, max=80))}
            ),
        )

    async def async_step_plane(self, user_input=None):
        errors = {}
        if user_input is not None:
            error = source_error(self.hass, self.planes, user_input)
            if error:
                errors["base"] = error
            else:
                self.planes.append({**user_input, "id": uuid4().hex})
                return await self.async_step_more()
        return self.async_show_form(
            step_id="plane", data_schema=plane_schema(user_input), errors=errors
        )

    async def async_step_more(self, user_input=None):
        if user_input is not None:
            if user_input["add_another"]:
                return await self.async_step_plane()
            return self.async_create_entry(title=self.title, data={"planes": self.planes})
        return self.async_show_form(
            step_id="more",
            data_schema=vol.Schema({vol.Required("add_another", default=False): bool}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    """Edit tuning or add/edit/remove planes, preserving identity on edits."""

    def __init__(self):
        self.editing = None

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init", menu_options=["tuning", "add_plane", "edit_plane", "remove_plane"]
        )

    async def async_step_tuning(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input["off_ratio"] >= user_input["on_ratio"]:
                errors["base"] = "threshold_order"
            else:
                return self.async_create_entry(title="", data=user_input)
        defaults = DEFAULTS | dict(self.config_entry.options) | (user_input or {})
        ranges = {
            "smoothing_seconds": (0, 600),
            "on_ratio": (0.5, 1.5),
            "off_ratio": (0.45, 1.4),
            "on_delay": (0, 300),
            "off_delay": (0, 600),
            "condition_delay": (0, 900),
            "stale_seconds": (15, 3600),
            "min_elevation": (1, 30),
            "min_expected_fraction": (0.005, 0.2),
        }
        return self.async_show_form(
            step_id="tuning",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(key, default=defaults[key]): number(*limits)
                    for key, limits in ranges.items()
                }
            ),
        )

    def _save(self, planes):
        self.hass.config_entries.async_update_entry(self.config_entry, data={"planes": planes})
        return self.async_create_entry(title="", data=dict(self.config_entry.options))

    async def async_step_add_plane(self, user_input=None):
        errors = {}
        if user_input is not None:
            planes = deepcopy(self.config_entry.data["planes"])
            error = source_error(self.hass, planes, user_input)
            if error:
                errors["base"] = error
            else:
                planes.append({**user_input, "id": uuid4().hex})
                return self._save(planes)
        return self.async_show_form(
            step_id="add_plane", data_schema=plane_schema(user_input), errors=errors
        )

    async def async_step_edit_plane(self, user_input=None):
        if user_input is not None:
            self.editing = user_input["plane"]
            return await self.async_step_update_plane()
        return self._select("edit_plane")

    async def async_step_update_plane(self, user_input=None):
        planes = deepcopy(self.config_entry.data["planes"])
        original = next(p for p in planes if p["id"] == self.editing)
        errors = {}
        if user_input is not None:
            error = source_error(self.hass, planes, user_input, self.editing)
            if error:
                errors["base"] = error
            else:
                original.update(user_input)
                return self._save(planes)
        return self.async_show_form(
            step_id="update_plane", data_schema=plane_schema(user_input or original), errors=errors
        )

    async def async_step_remove_plane(self, user_input=None):
        planes = self.config_entry.data["planes"]
        if len(planes) == 1:
            return self.async_abort(reason="last_plane")
        if user_input is not None:
            return self._save([p for p in planes if p["id"] != user_input["plane"]])
        return self._select("remove_plane")

    def _select(self, step):
        return self.async_show_form(
            step_id=step,
            data_schema=vol.Schema(
                {
                    vol.Required("plane"): vol.In(
                        {p["id"]: p["name"] for p in self.config_entry.data["planes"]}
                    )
                }
            ),
        )
