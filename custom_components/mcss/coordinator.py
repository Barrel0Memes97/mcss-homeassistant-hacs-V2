from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import timedelta
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MCSSApi
from .const import (
    CONF_API_KEY_ENTITY, CONF_CONSOLE_INTERVAL, CONF_CONSOLE_LINES,
    CONF_HOST, CONF_PLAYER_INTERVAL, CONF_SCAN_INTERVAL,
    DEFAULT_CONSOLE_INTERVAL, DEFAULT_CONSOLE_LINES,
    DEFAULT_PLAYER_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_PLAYER_RE = re.compile(
    r"There are\s+\d+\s+of a max of\s+\d+\s+players online:\s*(.*)$",
    re.IGNORECASE,
)


def parse_players(lines: list[str]) -> list[str] | None:
    for line in reversed(lines):
        match = _PLAYER_RE.search(str(line).strip())
        if match:
            names = match.group(1).strip()
            return [] if not names else [x.strip() for x in names.split(",") if x.strip()]
    return None


class MCSSCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.hass = hass

        options = entry.options
        self.scan_seconds = int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.console_seconds = int(options.get(CONF_CONSOLE_INTERVAL, DEFAULT_CONSOLE_INTERVAL))
        self.console_lines = int(options.get(CONF_CONSOLE_LINES, DEFAULT_CONSOLE_LINES))
        self.player_seconds = int(options.get(CONF_PLAYER_INTERVAL, DEFAULT_PLAYER_INTERVAL))

        self.api: MCSSApi | None = None
        self._last_console = 0.0
        self._last_players = 0.0
        self._console_cache: dict[str, list[str]] = {}
        self._player_cache: dict[str, list[str]] = {}
        self._icon_cache: dict[str, bytes] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_seconds),
        )

    @property
    def api_key(self) -> str:
        entity_id = self.entry.data[CONF_API_KEY_ENTITY]
        state = self.hass.states.get(entity_id)
        return state.state if state and state.state not in ("unknown", "unavailable") else ""

    def _make_api(self) -> MCSSApi:
        return MCSSApi(
            async_get_clientsession(self.hass),
            self.entry.data[CONF_HOST],
            self.api_key,
        )

    async def _async_update_data(self):
        if not self.api_key:
            raise UpdateFailed("The configured API-key input_text is empty or unavailable.")

        self.api = self._make_api()

        try:
            raw = await self.api.get_servers()
            data = {}

            async def load(server):
                sid = str(server.get("serverId", ""))
                if not sid:
                    return
                item = dict(server)
                try:
                    stats = await self.api.get_stats(sid)
                    item["stats"] = stats.get("latest", {}) if isinstance(stats, dict) else {}
                except Exception as err:
                    _LOGGER.warning("Stats failed for %s: %s", sid, err)
                    item["stats"] = {}
                data[sid] = item

            await asyncio.gather(*(load(s) for s in raw))

            now = time.monotonic()
            if now - self._last_console >= self.console_seconds:
                await self._refresh_console(data)
                self._last_console = now

            if now - self._last_players >= self.player_seconds:
                await self._refresh_players(data)
                self._last_players = now

            for sid, item in data.items():
                item["console"] = list(self._console_cache.get(sid, []))
                item["players"] = list(self._player_cache.get(sid, []))
                item["icon"] = self._icon_cache.get(sid)

            return data

        except (ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"MCSS API request failed: {err}") from err

    async def _refresh_console(self, data):
        async def one(sid):
            try:
                self._console_cache[sid] = [
                    str(x) for x in await self.api.get_console(
                        sid, self.console_lines, reversed_order=False
                    )
                ]
            except Exception as err:
                _LOGGER.debug("Console refresh failed for %s: %s", sid, err)

            if sid not in self._icon_cache:
                try:
                    self._icon_cache[sid] = await self.api.get_icon(sid)
                except Exception:
                    self._icon_cache[sid] = b""

        await asyncio.gather(*(one(sid) for sid in data))

    async def _refresh_players(self, data):
        # MCSS v2 exposes player count but not a player-name endpoint.
        # Ask normal Minecraft Java servers for "list", then parse their response.
        async def issue(sid, item):
            if item.get("stats", {}).get("playersOnline", 0) <= 0:
                self._player_cache[sid] = []
                return
            try:
                await self.api.command(sid, "list")
            except Exception as err:
                _LOGGER.debug("Player-list command failed for %s: %s", sid, err)

        await asyncio.gather(*(issue(sid, item) for sid, item in data.items()))
        await asyncio.sleep(0.15)

        async def read(sid):
            try:
                lines = await self.api.get_console(sid, 15, reversed_order=True)
                parsed = parse_players([str(x) for x in lines])
                if parsed is not None:
                    self._player_cache[sid] = parsed
            except Exception as err:
                _LOGGER.debug("Player-list parse failed for %s: %s", sid, err)

        await asyncio.gather(*(read(sid) for sid in data))

    async def async_send_command(self, server_id: str, command: str):
        self.api = self.api or self._make_api()
        await self.api.command(server_id, command)
        await self.async_request_refresh()

    async def async_action(self, server_id: str, action: int):
        self.api = self.api or self._make_api()
        await self.api.action(server_id, action)
        await self.async_request_refresh()

    async def async_get_icon(self, server_id: str):
        self.api = self.api or self._make_api()
        try:
            data = await self.api.get_icon(server_id)
            self._icon_cache[server_id] = data
            return data
        except Exception:
            return None
