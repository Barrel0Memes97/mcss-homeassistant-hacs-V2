from __future__ import annotations
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator import MCSSCoordinator


class MCSSEntity(CoordinatorEntity[MCSSCoordinator], Entity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, server_id):
        super().__init__(coordinator)
        self.server_id = server_id
        self._gone = False

    @property
    def server(self):
        return self.coordinator.data.get(self.server_id, {})

    @property
    def available(self):
        return not self._gone and bool(self.server)

    @property
    def device_info(self):
        server = self.server
        return {
            "identifiers": {(DOMAIN, self.server_id)},
            "name": server.get("name", self.server_id),
            "manufacturer": "MC Server Soft",
            "model": server.get("type", "Minecraft Server"),
            "configuration_url": self.coordinator.entry.data.get("host"),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        async def update():
            if self.server_id not in self.coordinator.data:
                self._gone = True
            else:
                self._gone = False
            self.async_write_ha_state()

        self.async_on_remove(self.coordinator.async_add_listener(update))
