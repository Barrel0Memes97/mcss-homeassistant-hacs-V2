from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import MCSSApi
from .const import (
    CONF_API_KEY_ENTITY, CONF_CONSOLE_INTERVAL, CONF_CONSOLE_LINES,
    CONF_HOST, CONF_PLAYER_INTERVAL, CONF_SCAN_INTERVAL,
    DEFAULT_CONSOLE_INTERVAL, DEFAULT_CONSOLE_LINES,
    DEFAULT_PLAYER_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN,
)


class MCSSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            host = user_input[CONF_HOST].rstrip("/")
            entity_id = user_input[CONF_API_KEY_ENTITY]
            state = self.hass.states.get(entity_id)
            if not state or state.state in ("", "unknown", "unavailable"):
                errors["api_key_entity"] = "invalid_key_entity"
            else:
                try:
                    api = MCSSApi(
                        async_get_clientsession(self.hass), host, state.state
                    )
                    await api.get_servers()
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="MC Server Soft",
                        data={
                            CONF_HOST: host,
                            CONF_API_KEY_ENTITY: entity_id,
                        },
                        options={
                            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                            CONF_CONSOLE_INTERVAL: DEFAULT_CONSOLE_INTERVAL,
                            CONF_CONSOLE_LINES: DEFAULT_CONSOLE_LINES,
                            CONF_PLAYER_INTERVAL: DEFAULT_PLAYER_INTERVAL,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default="http://192.168.254.74:25566"): str,
                vol.Required(CONF_API_KEY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="input_text")
                ),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MCSSOptionsFlow(config_entry)


class MCSSOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
                vol.Required(
                    CONF_CONSOLE_INTERVAL,
                    default=current.get(CONF_CONSOLE_INTERVAL, DEFAULT_CONSOLE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required(
                    CONF_CONSOLE_LINES,
                    default=current.get(CONF_CONSOLE_LINES, DEFAULT_CONSOLE_LINES),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=500)),
                vol.Required(
                    CONF_PLAYER_INTERVAL,
                    default=current.get(CONF_PLAYER_INTERVAL, DEFAULT_PLAYER_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
            }),
        )
