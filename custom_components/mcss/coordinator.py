from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import timedelta

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import MCSSApi
from .const import (
    CONF_API_KEY_ENTITY,
    CONF_CONSOLE_INTERVAL,
    CONF_CONSOLE_LINES,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    DEFAULT_CONSOLE_INTERVAL,
    DEFAULT_CONSOLE_LINES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_LOG_PREFIX_RE = re.compile(
    r"^\[[^\]]+\]\s+\[[^\]]+\]\s+(?:\[[^\]]+\]\s+)?(?:[^:]+:\s*)?(.*)$"
)
_PLAYER_HEADER_RE = re.compile(
    r"There are\s+(\d+)\s*/\s*(\d+)\s+players online\s*:",
    re.IGNORECASE,
)


def _message_text(line: str) -> str:
    """Strip the normal Forge/vanilla console prefix."""
    value = str(line).strip()
    match = _LOG_PREFIX_RE.match(value)
    return match.group(1).strip() if match else value


def parse_players(lines: list[str]) -> list[str] | None:
    """Parse the standard Minecraft Java 'list' console response.

    Handles both:
      There are 1/10 players online:
      Alex

    and the common single-line form:
      There are 1/10 players online: Alex
    """
    messages = [_message_text(line) for line in lines]

    for index, message in enumerate(messages):
        match = _PLAYER_HEADER_RE.search(message)
        if not match:
            continue

        expected = int(match.group(1))
        remainder = message[match.end():].strip()

        candidates = []
        if remainder:
            candidates.extend(
                x.strip() for x in remainder.split(",") if x.strip()
            )

        # Forge commonly prints player names on following console lines.
        for following in messages[index + 1:index + 1 + expected + 2]:
            if not following:
                continue
            if _PLAYER_HEADER_RE.search(following):
                break
            # Ignore obvious server-log messages; keep ordinary player-name lines.
            if following.startswith(("There are ", "Online players:")):
                continue
            candidates.extend(
                x.strip() for x in following.split(",") if x.strip()
            )
            if len(candidates) >= expected:
                break

        return candidates[:expected]

    return None


class MCSSCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    def __init__(self, hass, entry: ConfigEntry) -> None:
        self.entry = entry
        self.hass = hass

        options = entry.options
        self.scan_seconds = int(
            options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        self.console_seconds = int(
            options.get(CONF_CONSOLE_INTERVAL, DEFAULT_CONSOLE_INTERVAL)
        )
        self.console_lines = int(
            options.get(CONF_CONSOLE_LINES, DEFAULT_CONSOLE_LINES)
        )

        self.api = None
        self._last_console = 0.0
        self._last_players = 0.0
        self._console_cache = {}
        self._player_cache = {}
        self._icon_cache = {}

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
        return (
            state.state
            if state and state.state not in ("unknown", "unavailable")
            else ""
        )

    def _make_api(self):
        return MCSSApi(
            async_get_clientsession(self.hass),
            self.entry.data[CONF_HOST],
            self.api_key,
        )

    async def _async_update_data(self):
        if not self.api_key:
            raise UpdateFailed(
                "The configured API-key input_text is empty or unavailable."
            )

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
                    item["stats"] = (
                        stats.get("latest", {})
                        if isinstance(stats, dict)
                        else {}
                    )
                except Exception as err:
                    _LOGGER.warning("Stats failed for %s: %s", sid, err)
                    item["stats"] = {}

                data[sid] = item

            await asyncio.gather(*(load(server) for server in raw))

            now = time.monotonic()

            if now - self._last_console >= self.console_seconds:
                await self._refresh_console(data)
                self._last_console = now

            # Player discovery is tied to the normal update interval. This
            # prevents a second hidden polling loop and keeps the setting
            # predictable.
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
                    str(x)
                    for x in await self.api.get_console(
                        sid,
                        self.console_lines,
                        reversed_order=False,
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
        async def issue(sid, item):
            if item.get("stats", {}).get("playersOnline", 0) <= 0:
                self._player_cache[sid] = []
                return

            try:
                await self.api.command(sid, "list")
            except Exception as err:
                _LOGGER.debug(
                    "Player-list command failed for %s: %s", sid, err
                )

        await asyncio.gather(
            *(issue(sid, item) for sid, item in data.items())
        )

        # Give MCSS/Minecraft enough time to write the command response.
        await asyncio.sleep(0.25)

        async def read(sid):
            try:
                # Read enough lines to catch the header plus following
                # player-name lines.
                lines = await self.api.get_console(
                    sid, max(25, self.console_lines), reversed_order=False
                )
                parsed = parse_players([str(x) for x in lines])
                if parsed is not None:
                    self._player_cache[sid] = parsed
            except Exception as err:
                _LOGGER.debug(
                    "Player-list parse failed for %s: %s", sid, err
                )

        await asyncio.gather(*(read(sid) for sid in data))

    async def async_send_command(self, server_id, command):
        self.api = self.api or self._make_api()
        await self.api.command(server_id, command)
        await self.async_request_refresh()

    async def async_action(self, server_id, action):
        self.api = self.api or self._make_api()
        await self.api.action(server_id, action)
        await self.async_request_refresh()

    async def async_get_icon(self, server_id):
        self.api = self.api or self._make_api()
        try:
            data = await self.api.get_icon(server_id)
            self._icon_cache[server_id] = data
            return data
        except Exception:
            return None
