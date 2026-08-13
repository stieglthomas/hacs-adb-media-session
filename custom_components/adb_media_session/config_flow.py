"""Config flow for ADB Media Session integration."""

from __future__ import annotations

import logging
from typing import Any

from adb_shell.exceptions import AdbCommandFailureException, DeviceAuthError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .adb_client import ADBClient, async_get_or_create_rsa_key
from .const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=DEFAULT_SCAN_INTERVAL,
        ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
    }
)


class AdbMediaSessionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ADB Media Session."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user input step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            name = user_input.get(CONF_NAME, DEFAULT_NAME)
            interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                priv_key, pub_key = await async_get_or_create_rsa_key(self.hass)
                client = ADBClient(host, port, priv_key, pub_key)

                await client.connect()

                # Verify shell access
                output = await client.shell("dumpsys media_session", timeout=5.0)
                await client.close()

                if not output:
                    errors["base"] = "shell_unavailable"
                else:
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_NAME: name,
                            CONF_SCAN_INTERVAL: interval,
                        },
                    )

            except DeviceAuthError:
                errors["base"] = "authorization_required"
            except ConnectionRefusedError:
                errors["base"] = "cannot_connect"
            except TimeoutError:
                errors["base"] = "cannot_connect"
            except OSError:
                errors["base"] = "cannot_connect"
            except AdbCommandFailureException:
                errors["base"] = "shell_unavailable"
            except Exception as err:
                _LOGGER.exception("Unexpected exception in config flow: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
