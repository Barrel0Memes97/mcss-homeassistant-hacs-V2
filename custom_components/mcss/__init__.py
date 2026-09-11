from __future__ import annotations
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from .const import (
    ACTION_KILL, ACTION_RESTART, ACTION_START, ACTION_STOP,
    ATTR_ACTION, ATTR_COMMAND, ATTR_SERVER_ID, DOMAIN,
    PLATFORMS, SERVICE_SEND_COMMAND, SERVICE_SERVER_ACTION,
)
from .coordinator import MCSSCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = MCSSCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def send_command(call: ServiceCall):
        sid = call.data[ATTR_SERVER_ID]
        command = call.data[ATTR_COMMAND].strip()
        if sid not in coordinator.data:
            raise HomeAssistantError(f"Unknown MCSS server: {sid}")
        if not command:
            raise HomeAssistantError("Command cannot be empty.")
        await coordinator.async_send_command(sid, command)

    async def server_action(call: ServiceCall):
        sid = call.data[ATTR_SERVER_ID]
        action = int(call.data[ATTR_ACTION])
        if sid not in coordinator.data:
            raise HomeAssistantError(f"Unknown MCSS server: {sid}")
        if action not in (ACTION_STOP, ACTION_START, ACTION_KILL, ACTION_RESTART):
            raise HomeAssistantError("Invalid MCSS action.")
        await coordinator.async_action(sid, action)

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, send_command,
        schema=vol.Schema({
            vol.Required(ATTR_SERVER_ID): str,
            vol.Required(ATTR_COMMAND): str,
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SERVER_ACTION, server_action,
        schema=vol.Schema({
            vol.Required(ATTR_SERVER_ID): str,
            vol.Required(ATTR_ACTION): vol.Coerce(int),
        }),
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR, Platform.BUTTON, Platform.CAMERA, Platform.TEXT]
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    hass.services.async_remove(DOMAIN, SERVICE_SEND_COMMAND)
    hass.services.async_remove(DOMAIN, SERVICE_SERVER_ACTION)
    return unloaded
