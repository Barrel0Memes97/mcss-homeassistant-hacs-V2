from __future__ import annotations
from homeassistant.components.text import TextEntity
from .const import DOMAIN
from .entity import MCSSEntity


class MCSSCommandText(MCSSEntity, TextEntity):
    _attr_native_max = 500
    _attr_native_min = 0
    _attr_mode = "text"

    def __init__(self, coordinator, server_id):
        super().__init__(coordinator, server_id)
        self._attr_unique_id = f"{server_id}_console_command"
        self._attr_name = "Console command"
        self._attr_icon = "mdi:console-line"
        self._attr_native_value = ""

    async def async_set_value(self, value: str):
        value = value.strip()
        if value:
            await self.coordinator.async_send_command(self.server_id, value)
        self._attr_native_value = ""
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = {}

    def sync():
        new = []
        for sid in coordinator.data:
            if sid not in entities:
                entities[sid] = MCSSCommandText(coordinator, sid)
                new.append(entities[sid])
        if new:
            async_add_entities(new)

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))
