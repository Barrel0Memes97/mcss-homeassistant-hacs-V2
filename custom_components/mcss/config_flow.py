from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MCSSApi
from .const import (
    CONF_API_KEY_ENTITY,
    CONF_CONSOLE_INTERVAL,
    CONF_CONSOLE_LINES,
    CONF_HOST,
    CONF_PLAYER_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_CONSOLE_INTERVAL,
    DEFAULT_CONSOLE_LINES,
    DEFAULT_PLAYER_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
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
                vol.Required(
                    CONF_HOST,
                    default="http://192.168.254.74:25560",
                ): str,
                vol.Required(CONF_API_KEY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="input_text")
                ),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MCSSOptionsFlow()

    async def async_step_reconfigure(self, user_input=None):
        """Allow the MCSS URL and API-key entity to be changed."""
        errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST].rstrip("/")
            api_entity = user_input[CONF_API_KEY_ENTITY]
            state = self.hass.states.get(api_entity)

            if not state or state.state in ("", "unknown", "unavailable"):
                errors["api_key_entity"] = "invalid_key_entity"
            else:
                try:
                    api = MCSSApi(
                        async_get_clientsession(self.hass),
                        host,
                        state.state,
                    )
                    await api.get_servers()
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={
                            CONF_HOST: host,
                            CONF_API_KEY_ENTITY: api_entity,
                        },
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_HOST,
                    default=entry.data.get(
                        CONF_HOST, "http://192.168.254.74:25560"
                    ),
                ): str,
                vol.Required(
                    CONF_API_KEY_ENTITY,
                    default=entry.data.get(CONF_API_KEY_ENTITY, ""),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="input_text")
                ),
            }),
            errors=errors,
        )


class MCSSOptionsFlow(config_entries.OptionsFlow):
    """Integration settings shown by Configure."""

    async def async_step_init(self, user_input=None):
        if user_input:
            host = user_input[CONF_HOST].rstrip("/")
            api_entity = user_input[CONF_API_KEY_ENTITY]
            state = self.hass.states.get(api_entity)

            if not state or state.state in ("", "unknown", "unavailable"):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(user_input),
                    errors={"api_key_entity": "invalid_key_entity"},
                )

            try:
                api = MCSSApi(
                    async_get_clientsession(self.hass),
                    host,
                    state.state,
                )
                await api.get_servers()
            except Exception:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(user_input),
                    errors={"base": "cannot_connect"},
                )

            # URL and API-key entity are connection settings, so keep them in
            # config-entry data while the timing/history values live in options.
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_HOST: host,
                    CONF_API_KEY_ENTITY: api_entity,
                },
            )

            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_CONSOLE_INTERVAL: int(user_input[CONF_CONSOLE_INTERVAL]),
                    CONF_CONSOLE_LINES: int(user_input[CONF_CONSOLE_LINES]),
                    CONF_PLAYER_INTERVAL: int(
                        user_input[CONF_PLAYER_INTERVAL]
                    ),
                },
            )

        current = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=self._schema({
                CONF_HOST: self.config_entry.data.get(
                    CONF_HOST, "http://192.168.254.74:25560"
                ),
                CONF_API_KEY_ENTITY: self.config_entry.data.get(
                    CONF_API_KEY_ENTITY, ""
                ),
                CONF_SCAN_INTERVAL: current.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
                CONF_CONSOLE_INTERVAL: current.get(
                    CONF_CONSOLE_INTERVAL, DEFAULT_CONSOLE_INTERVAL
                ),
                CONF_CONSOLE_LINES: current.get(
                    CONF_CONSOLE_LINES, DEFAULT_CONSOLE_LINES
                ),
                CONF_PLAYER_INTERVAL: current.get(
                    CONF_PLAYER_INTERVAL, DEFAULT_PLAYER_INTERVAL
                ),
            }),
        )

    @staticmethod
    def _schema(values):
        return vol.Schema({
            vol.Required(
                CONF_HOST,
                default=values.get(CONF_HOST, ""),
            ): str,
            vol.Required(
                CONF_API_KEY_ENTITY,
                default=values.get(CONF_API_KEY_ENTITY, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="input_text")
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
            vol.Required(
                CONF_CONSOLE_INTERVAL,
                default=values.get(
                    CONF_CONSOLE_INTERVAL, DEFAULT_CONSOLE_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
            vol.Required(
                CONF_CONSOLE_LINES,
                default=values.get(
                    CONF_CONSOLE_LINES, DEFAULT_CONSOLE_LINES
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
            vol.Required(
                CONF_PLAYER_INTERVAL,
                default=values.get(
                    CONF_PLAYER_INTERVAL,
                    DEFAULT_PLAYER_INTERVAL,
                ),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=5, max=600),
            ),
        })
