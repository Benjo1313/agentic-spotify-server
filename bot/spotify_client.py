"""Spotify Web API client with OAuth2 token management."""

import asyncio
import base64
import time
from typing import Any

import aiohttp


SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = " ".join([
    "user-modify-playback-state",
    "user-read-playback-state",
    "user-read-currently-playing",
    "user-read-recently-played",
])


class SpotifyError(Exception):
    pass


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._token_expiry: float = 0.0
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        await self._ensure_token()
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    async def _ensure_token(self) -> None:
        if self._access_token and time.time() < self._token_expiry - 60:
            return
        await self._refresh_access_token()

    async def _refresh_access_token(self) -> None:
        credentials = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()

        async with self._session.post(
            SPOTIFY_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise SpotifyError(f"Token refresh failed ({resp.status}): {text}")
            data = await resp.json()

        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data["expires_in"]

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: Any = None,
    ) -> dict | None:
        await self._ensure_token()
        url = f"{SPOTIFY_API_BASE}{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        async with self._session.request(
            method, url, headers=headers, params=params, json=json
        ) as resp:
            if resp.status == 204:
                return None
            if not resp.ok:
                text = await resp.text()
                raise SpotifyError(f"{method} {path} failed ({resp.status}): {text}")
            return await resp.json()

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search for tracks. Returns list of track objects."""
        result = await self._request("GET", "/search", params={
            "q": query,
            "type": "track",
            "limit": limit,
        })
        return result["tracks"]["items"]

    async def get_playback(self) -> dict | None:
        """Get current playback state. Returns None if nothing is playing."""
        return await self._request("GET", "/me/player")

    async def play(self, device_id: str | None = None, uris: list[str] | None = None, context_uri: str | None = None) -> None:
        """Start or resume playback."""
        body: dict = {}
        if uris:
            body["uris"] = uris
        if context_uri:
            body["context_uri"] = context_uri
        params = {"device_id": device_id} if device_id else None
        await self._request("PUT", "/me/player/play", params=params, json=body)

    async def pause(self, device_id: str | None = None) -> None:
        """Pause playback."""
        params = {"device_id": device_id} if device_id else None
        await self._request("PUT", "/me/player/pause", params=params)

    async def skip(self, device_id: str | None = None) -> None:
        """Skip to next track."""
        params = {"device_id": device_id} if device_id else None
        await self._request("POST", "/me/player/next", params=params)

    async def add_to_queue(self, uri: str, device_id: str | None = None) -> None:
        """Add a track URI to the playback queue."""
        params: dict = {"uri": uri}
        if device_id:
            params["device_id"] = device_id
        await self._request("POST", "/me/player/queue", params=params)

    async def get_queue(self) -> dict:
        """Get the current playback queue."""
        return await self._request("GET", "/me/player/queue")

    async def get_devices(self) -> list[dict]:
        """List available Spotify devices."""
        result = await self._request("GET", "/me/player/devices")
        return result["devices"]
