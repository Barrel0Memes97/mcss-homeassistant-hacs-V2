from __future__ import annotations
from homeassistant.components.camera import Camera
from .const import DOMAIN
from .entity import MCSSEntity


class MCSSIconCamera(MCSSEntity, Camera):
    def __init__(self, coordinator, server_id):
        Camera.__init__(self)
        MCSSEntity.__init__(self, coordinator, server_id)
        self._attr_unique_id = f"{server_id}_icon"
        self._attr_name = "Server icon"
        self._attr_icon = "mdi:minecraft"
        self._attr_content_type = "image/png"

    @property
    def available(self):
        return bool(self.server) and bool(self.server.get("icon"))

    async def async_camera_image(self, width=None, height=None):
        return self.server.get("icon") or await self.coordinator.async_get_icon(self.server_id)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = {}

    def sync():
        new = []
        for sid in coordinator.data:
            if sid not in entities:
                entities[sid] = MCSSIconCamera(coordinator, sid)
                new.append(entities[sid])
        if new:
            async_add_entities(new)

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))
