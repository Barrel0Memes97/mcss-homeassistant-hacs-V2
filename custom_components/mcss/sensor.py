from __future__ import annotations

from datetime import datetime, timezone
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfInformation
from .const import DOMAIN
from .entity import MCSSEntity


def duration_text(seconds: int) -> str:
    seconds = max(0, int(seconds))
    weeks, rem = divmod(seconds, 604800)
    days, rem = divmod(rem, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    clock = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    if weeks:
        return f"{weeks}w {days}d {clock}"
    if days:
        return f"{days}d {clock}"
    return clock


class MCSSSensor(MCSSEntity, SensorEntity):
    def __init__(self, coordinator, server_id, kind):
        super().__init__(coordinator, server_id)
        self.kind = kind
        self._attr_unique_id = f"{server_id}_{kind}"

    @property
    def name(self):
        return {
            "status": "Status",
            "players": "Players",
            "player_list": "Player list",
            "cpu": "CPU",
            "memory": "Memory used",
            "memory_percent": "Memory usage",
            "uptime": "Uptime",
            "uptime_text": "Uptime display",
            "console": "Latest console output",
        }[self.kind]

    @property
    def native_value(self):
        s = self.server
        st = s.get("stats", {})
        if self.kind == "status":
            return "Running" if s.get("status") == 1 else "Offline"
        if self.kind == "players":
            return st.get("playersOnline", 0)
        if self.kind == "player_list":
            players = s.get("players", [])
            return ", ".join(players) if players else "No players"
        if self.kind == "cpu":
            return st.get("cpu", 0)
        if self.kind == "memory":
            return st.get("memoryUsed", 0)
        if self.kind == "memory_percent":
            limit = st.get("memoryLimit", 0)
            return round(st.get("memoryUsed", 0) * 100 / limit, 1) if limit else 0
        if self.kind in ("uptime", "uptime_text"):
            start = int(st.get("startDate", 0) or 0)
            if not start or s.get("status") != 1:
                return 0 if self.kind == "uptime" else "00:00:00"
            elapsed = int(datetime.now(timezone.utc).timestamp()) - start
            return elapsed if self.kind == "uptime" else duration_text(elapsed)
        if self.kind == "console":
            lines = s.get("console", [])
            return lines[-1] if lines else "No console output"
        return None

    @property
    def extra_state_attributes(self):
        s = self.server
        if self.kind in ("players", "player_list"):
            return {
                "players": s.get("players", []),
                "player_count": len(s.get("players", [])),
            }
        if self.kind == "console":
            return {"lines": s.get("console", [])}
        return None

    @property
    def native_unit_of_measurement(self):
        return {
            "cpu": PERCENTAGE,
            "memory": UnitOfInformation.MEGABYTES,
            "memory_percent": PERCENTAGE,
            "uptime": "s",
        }.get(self.kind)

    @property
    def icon(self):
        return {
            "status": "mdi:minecraft",
            "players": "mdi:account-group",
            "player_list": "mdi:account-multiple",
            "cpu": "mdi:cpu-64-bit",
            "memory": "mdi:memory",
            "memory_percent": "mdi:memory",
            "uptime": "mdi:timer-outline",
            "uptime_text": "mdi:timer-outline",
            "console": "mdi:console",
        }[self.kind]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = {}
    kinds = (
        "status", "players", "player_list", "cpu", "memory",
        "memory_percent", "uptime", "uptime_text", "console",
    )

    def sync():
        new = []
        for sid in coordinator.data:
            for kind in kinds:
                key = (sid, kind)
                if key not in entities:
                    entities[key] = MCSSSensor(coordinator, sid, kind)
                    new.append(entities[key])
        if new:
            async_add_entities(new)

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))
