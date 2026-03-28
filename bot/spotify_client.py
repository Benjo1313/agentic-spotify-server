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
    "playlist-read-private",
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
            if "json" in (resp.content_type or ""):
                return await resp.json()
            return None

    async def search(self, query: str, type: str = "track", limit: int = 10) -> list[dict]:
        """Search Spotify. Returns list of items for the given type (track/album/artist/playlist)."""
        result = await self._request("GET", "/search", params={
            "q": query,
            "type": type,
            "limit": limit,
        })
        return result[f"{type}s"]["items"]

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

    async def previous(self, device_id: str | None = None) -> None:
        """Skip to the previous track."""
        params = {"device_id": device_id} if device_id else None
        await self._request("POST", "/me/player/previous", params=params)

    async def set_shuffle(self, state: bool, device_id: str | None = None) -> None:
        """Enable or disable shuffle mode."""
        params: dict = {"state": "true" if state else "false"}
        if device_id:
            params["device_id"] = device_id
        await self._request("PUT", "/me/player/shuffle", params=params)

    async def set_repeat(self, state: str, device_id: str | None = None) -> None:
        """Set repeat mode. state must be 'off', 'track', or 'context'."""
        params: dict = {"state": state}
        if device_id:
            params["device_id"] = device_id
        await self._request("PUT", "/me/player/repeat", params=params)

    async def seek(self, position_ms: int, device_id: str | None = None) -> None:
        """Seek to a position in the current track."""
        params: dict = {"position_ms": position_ms}
        if device_id:
            params["device_id"] = device_id
        await self._request("PUT", "/me/player/seek", params=params)

    async def get_recently_played(self, limit: int = 10) -> dict:
        """Get recently played tracks."""
        return await self._request("GET", "/me/player/recently-played", params={"limit": limit})

    async def get_playlists(self, limit: int = 20) -> dict:
        """Get the current user's playlists."""
        return await self._request("GET", "/me/playlists", params={"limit": limit})

    async def get_playlist_tracks(self, playlist_id: str, limit: int = 20) -> dict:
        """Get tracks in a playlist."""
        return await self._request("GET", f"/playlists/{playlist_id}/tracks", params={"limit": limit})

    async def get_devices(self) -> list[dict]:
        """List available Spotify devices."""
        result = await self._request("GET", "/me/player/devices")
        return result["devices"]
