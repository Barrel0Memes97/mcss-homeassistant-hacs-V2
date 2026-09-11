from __future__ import annotations
from homeassistant.components.button import ButtonEntity
from .const import ACTION_KILL, ACTION_RESTART, ACTION_START, ACTION_STOP, DOMAIN
from .entity import MCSSEntity


class MCSSButton(MCSSEntity, ButtonEntity):
    def __init__(self, coordinator, server_id, kind):
        super().__init__(coordinator, server_id)
        self.kind = kind
        self._attr_unique_id = f"{server_id}_{kind}"
        self._attr_name = {
            "start": "Start", "stop": "Stop", "restart": "Restart",
            "kill": "Kill", "refresh_players": "Refresh players",
        }[kind]
        self._attr_icon = {
            "start": "mdi:play", "stop": "mdi:stop",
            "restart": "mdi:restart", "kill": "mdi:skull",
            "refresh_players": "mdi:account-refresh",
        }[kind]

    async def async_press(self):
        if self.kind == "refresh_players":
            await self.coordinator.async_send_command(self.server_id, "list")
            return
        await self.coordinator.async_action(
            self.server_id,
            {
                "start": ACTION_START, "stop": ACTION_STOP,
                "restart": ACTION_RESTART, "kill": ACTION_KILL,
            }[self.kind],
        )


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = {}

    def sync():
        new = []
        for sid in coordinator.data:
            for kind in ("start", "stop", "restart", "kill", "refresh_players"):
                key = (sid, kind)
                if key not in entities:
                    entities[key] = MCSSButton(coordinator, sid, kind)
                    new.append(entities[key])
        if new:
            async_add_entities(new)

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))
