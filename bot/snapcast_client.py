"""Snapcast JSON-RPC API client.

Uses requests + asyncio.to_thread because Snapcast's HTTP server sends
Connection: close headers in a way that aiohttp's strict parser rejects.
"""

import asyncio
from difflib import SequenceMatcher
from functools import partial

import requests


SNAPCAST_URL = "http://localhost:1780/jsonrpc"


class SnapcastError(Exception):
    pass


class SnapcastClient:
    def __init__(self, url: str = SNAPCAST_URL):
        self._url = url
        self._id = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _call_sync(self, method: str, params: dict | None = None) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            payload["params"] = params

        resp = requests.post(self._url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise SnapcastError(f"{method} failed: {data['error']}")

        return data["result"]

    async def _call(self, method: str, params: dict | None = None) -> dict:
        fn = partial(self._call_sync, method, params)
        return await asyncio.to_thread(fn)

    async def get_status(self) -> dict:
        """Return full server status including all clients and groups."""
        return await self._call("Server.GetStatus")

    async def get_clients(self) -> list[dict]:
        """Return list of all connected clients."""
        status = await self.get_status()
        clients = []
        for group in status["server"]["groups"]:
            clients.extend(group["clients"])
        return clients

    async def set_volume(self, client_id: str, volume: int, muted: bool | None = None) -> None:
        """Set volume (0-100) for a client, preserving mute state unless muted is given."""
        volume = max(0, min(100, volume))
        if muted is None:
            status = await self.get_status()
            muted = self._find_client_muted(status, client_id)
        await self._call("Client.SetVolume", {
            "id": client_id,
            "volume": {"percent": volume, "muted": muted},
        })

    async def set_mute(self, client_id: str, muted: bool) -> None:
        """Mute or unmute a client without changing its volume level."""
        status = await self.get_status()
        current_vol = self._find_client_volume(status, client_id)
        await self.set_volume(client_id, current_vol, muted)

    async def set_stream(self, group_id: str, stream_id: str) -> None:
        """Switch a group to a different stream (e.g. 'Mopidy' or 'Spotify')."""
        await self._call("Group.SetStream", {"id": group_id, "stream_id": stream_id})

    async def resolve_client(self, name: str) -> str:
        """
        Resolve a friendly name to a Snapcast client ID.
        Matches against client name and host with fuzzy fallback.
        Raises SnapcastError if no match found.
        """
        clients = await self.get_clients()
        name_norm = _normalize(name)

        # Exact match first
        for client in clients:
            if name_norm in (_normalize(client["config"]["name"]), _normalize(client["host"]["name"])):
                return client["id"]

        # Fuzzy match
        best_score = 0.0
        best_id = None
        for client in clients:
            for candidate in (client["config"]["name"], client["host"]["name"]):
                score = SequenceMatcher(None, name_norm, _normalize(candidate)).ratio()
                if score > best_score:
                    best_score = score
                    best_id = client["id"]

        if best_score >= 0.6 and best_id:
            return best_id

        known = [c["config"]["name"] or c["host"]["name"] for c in clients]
        raise SnapcastError(f"No client matching '{name}'. Known clients: {known}")

    def _find_client_volume(self, status: dict, client_id: str) -> int:
        for group in status["server"]["groups"]:
            for client in group["clients"]:
                if client["id"] == client_id:
                    return client["config"]["volume"]["percent"]
        return 50

    def _find_client_muted(self, status: dict, client_id: str) -> bool:
        for group in status["server"]["groups"]:
            for client in group["clients"]:
                if client["id"] == client_id:
                    return client["config"]["volume"]["muted"]
        return False


def _normalize(s: str) -> str:
    return s.lower().replace(" ", "").replace("_", "").replace("-", "")
