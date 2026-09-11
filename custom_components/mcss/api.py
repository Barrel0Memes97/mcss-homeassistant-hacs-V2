from __future__ import annotations

from typing import Any
from aiohttp import ClientSession, ClientResponseError


class MCSSApi:
    def __init__(self, session: ClientSession, host: str, api_key: str) -> None:
        self._session = session
        self._host = host.rstrip("/")
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key, "Accept": "application/json"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = self._headers()
        extra = kwargs.pop("headers", None)
        if extra:
            headers.update(extra)

        async with self._session.request(
            method, f"{self._host}/api/v2{path}", headers=headers, **kwargs
        ) as response:
            if response.status >= 400:
                text = await response.text()
                raise ClientResponseError(
                    response.request_info,
                    response.history,
                    status=response.status,
                    message=text[:500],
                    headers=response.headers,
                )
            if response.content_type == "application/json":
                return await response.json()
            return await response.read()

    async def get_servers(self):
        data = await self._request("GET", "/servers")
        return data if isinstance(data, list) else []

    async def get_stats(self, server_id: str):
        return await self._request("GET", f"/servers/{server_id}/stats")

    async def get_console(self, server_id: str, amount: int, reversed_order=False):
        data = await self._request(
            "GET",
            f"/servers/{server_id}/console",
            params={
                "AmountOfLines": amount,
                "Reversed": str(reversed_order).lower(),
            },
        )
        return data if isinstance(data, list) else []

    async def get_icon(self, server_id: str) -> bytes:
        return await self._request("GET", f"/servers/{server_id}/icon")

    async def action(self, server_id: str, action: int):
        return await self._request(
            "POST",
            f"/servers/{server_id}/execute/action",
            json={"action": action},
        )

    async def command(self, server_id: str, command: str):
        return await self._request(
            "POST",
            f"/servers/{server_id}/execute/command",
            json={"command": command},
        )
