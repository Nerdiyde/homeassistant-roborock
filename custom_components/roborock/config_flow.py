"""Config flow for Roborock."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .api.api import RoborockClient
from .api.containers import UserData
from .const import (
    CONF_BASE_URL,
    CONF_ENTRY_CODE,
    CONF_ENTRY_USERNAME,
    CONF_USER_DATA,
    DOMAIN,
    CONF_SCALE,
    CONF_ROTATE,
    CONF_TRIM,
    CONF_MAP_TRANSFORM,
    CONF_LEFT,
    CONF_RIGHT,
    CONF_TOP,
    CONF_BOTTOM,
    CAMERA,
    VACUUM,
    CONF_INCLUDE_SHARED,
    CONF_ENTRY_PASSWORD,
)
from .utils import get_nested_dict, set_nested_dict

_LOGGER = logging.getLogger(__name__)


class RoborockFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roborock."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._username = None
        self._errors = {}
        self._username = None
        self._client = None
        self._auth_method = None

    async def async_step_reauth(self, _user_input=None):
        """Handle a reauth flow."""
        await self.hass.config_entries.async_remove(self.context["entry_id"])
        return self._show_user_form()

    async def async_step_user(self, _user_input=None):
        """Handle a flow initialized by the user."""
        return self._show_user_form()

    async def async_step_email(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input and user_input[CONF_ENTRY_USERNAME]:
            username = user_input[CONF_ENTRY_USERNAME]
            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()
            self._username = username
            if self._auth_method == CONF_ENTRY_CODE:
                client = await self._request_code(username)
                if client:
                    self._client = client
                    return self._show_code_form(user_input)
                else:
                    self._errors["base"] = "auth"
            elif self._auth_method == CONF_ENTRY_PASSWORD:
                client = RoborockClient(username)
                if client:
                    self._client = client
                    return self._show_password_form(user_input)
                else:
                    self._errors["base"] = "auth"
            return self._show_email_form(user_input)

        return self._show_email_form(user_input)

    async def async_step_code(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if not user_input:
            self._auth_method = CONF_ENTRY_CODE
            return self._show_email_form()

        username = self._username
        code = user_input[CONF_ENTRY_CODE]
        user_data = await self._code_login(code)
        if user_data:
            return self._create_entry(username, user_data)
        else:
            self._errors["base"] = "no_device"

        return self._show_code_form(user_input)

    async def async_step_password(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if not user_input:
            self._auth_method = CONF_ENTRY_PASSWORD
            return self._show_email_form()

        username = self._username
        code = user_input[CONF_ENTRY_PASSWORD]
        user_data = await self._pass_login(code)
        if user_data:
            return self._create_entry(username, user_data)
        else:
            self._errors["base"] = "no_device"

        return self._show_password_form(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RoborockOptionsFlowHandler(config_entry)

    def _show_user_form(self):
        """Show the configuration form to choose authentication method."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[CONF_ENTRY_CODE, CONF_ENTRY_PASSWORD]
        )

    def _show_email_form(self, user_input=None):
        """Show the configuration form to provide user email."""
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="email",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTRY_USERNAME, default=user_input.get(CONF_ENTRY_USERNAME)
                    ): str
                }
            ),
            errors=self._errors,
            last_step=False,
        )

    def _show_code_form(self, user_input):
        """Show the configuration form to provide authentication code."""
        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTRY_CODE, default=user_input.get(CONF_ENTRY_CODE)
                    ): str
                }
            ),
            errors=self._errors,
        )

    def _show_password_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to provide authentication code."""
        return self.async_show_form(
            step_id="password",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTRY_PASSWORD, default=user_input.get(CONF_ENTRY_PASSWORD)
                    ): str
                }
            ),
            errors=self._errors,
        )

    def _create_entry(self, username: str, user_data: UserData):
        return self.async_create_entry(
            title=username,
            data={
                CONF_ENTRY_USERNAME: username,
                CONF_USER_DATA: user_data.data,
                CONF_BASE_URL: self._client.base_url,
            },
        )

    async def _request_code(self, username: str):
        """Return true if credentials is valid."""
        try:
            _LOGGER.debug("Requesting code for Roborock account")
            client = RoborockClient(username)
            await client.request_code()
            return client
        except Exception as ex:
            _LOGGER.exception(ex)
            self._errors["base"] = "auth"
            return None

    async def _code_login(self, code) -> UserData | None:
        """Return UserData if login code is valid."""
        try:
            _LOGGER.debug("Logging into Roborock account using email provided code")
            login_data = await self._client.code_login(code)
            return login_data
        except Exception as ex:
            _LOGGER.exception(ex)
            self._errors["base"] = "auth"
            return

    async def _pass_login(self, password) -> UserData | None:
        """Return UserData if login code is valid."""
        try:
            _LOGGER.debug("Logging into Roborock account using email provided code")
            login_data = await self._client.pass_login(password)
            return login_data
        except Exception as ex:
            _LOGGER.exception(ex)
            self._errors["base"] = "auth"
            return


def discriminant(_, validators):
    return list(validators).__reversed__()


POSITIVE_FLOAT_SCHEMA = vol.All(vol.Coerce(float), vol.Range(min=0))
ROTATION_SCHEMA = vol.All(vol.Coerce(int), vol.Coerce(str), vol.In(["0", "90", "180", "270"]),
                          discriminant=discriminant)
PERCENT_SCHEMA = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))

CAMERA_VALUES = {
    f"{CONF_MAP_TRANSFORM}.{CONF_SCALE}": 1.0,
    f"{CONF_MAP_TRANSFORM}.{CONF_ROTATE}": 0,
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_LEFT}": 0.0,
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_RIGHT}": 0.0,
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_TOP}": 0.0,
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_BOTTOM}": 0.0,
}

CAMERA_SCHEMA = {
    f"{CONF_MAP_TRANSFORM}.{CONF_SCALE}": POSITIVE_FLOAT_SCHEMA,
    f"{CONF_MAP_TRANSFORM}.{CONF_ROTATE}": ROTATION_SCHEMA,
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_LEFT}": PERCENT_SCHEMA,
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_RIGHT}": PERCENT_SCHEMA,
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_TOP}": PERCENT_SCHEMA,
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_BOTTOM}": PERCENT_SCHEMA,
}

VACUUM_VALUES = {
    CONF_INCLUDE_SHARED: True
}

VACUUM_SCHEMA = {
    CONF_INCLUDE_SHARED: vol.Coerce(bool)
}

OPTION_VALUES = {
    VACUUM: VACUUM_VALUES,
    CAMERA: CAMERA_VALUES,
}

OPTION_SCHEMA = {
    **{f"{VACUUM}.{vs_key}": vs_value for vs_key, vs_value in VACUUM_SCHEMA.items()},
    **{f"{CAMERA}.{cs_key}": cs_value for cs_key, cs_value in CAMERA_SCHEMA.items()},
}


class RoborockOptionsFlowHandler(config_entries.OptionsFlow):
    """Roborock config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, _=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, _user_input=None):
        """Handle a flow initialized by the user."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[CAMERA, VACUUM],
        )

    async def async_step_camera(self, user_input=None):
        return await self._async_step_platform(CAMERA, CAMERA_SCHEMA, CAMERA_VALUES, user_input)

    async def async_step_vacuum(self, user_input=None):
        return await self._async_step_platform(VACUUM, VACUUM_SCHEMA, VACUUM_VALUES, user_input)

    async def _async_step_platform(self, platform: str, schema: dict[str, Any], values: dict[str, Any],
                                   user_input=None):
        if user_input:
            data = {}
            for key, value in user_input.items():
                set_nested_dict(data, key, value)
            if self.options:
                self.options[platform] = data
            else:
                self.options = {platform: data}
            return await self._update_options()
        options = self.options.get(platform) if self.options else None
        return self.async_show_form(
            step_id=platform,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        key, default=schema.get(key)(get_nested_dict(options or {}, key, value))
                    ): schema.get(key)
                    for key, value in values.items()
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(title="", data=self.options)
