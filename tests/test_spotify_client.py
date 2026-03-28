"""Tests for SpotifyClient._request response handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.spotify_client import SpotifyClient, SpotifyError


def _make_client() -> SpotifyClient:
    client = SpotifyClient("id", "secret", "refresh")
    client._access_token = "tok"
    client._token_expiry = 9999999999.0
    return client


def _mock_response(status: int, content_type: str, body: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.ok = status < 400
    resp.content_type = content_type
    resp.text = AsyncMock(return_value=body)
    resp.json = AsyncMock(side_effect=Exception("json() should not be called"))
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


async def test_request_204_returns_none():
    """204 No Content must return None without calling resp.json()."""
    client = _make_client()
    resp = _mock_response(204, "")
    client._session = MagicMock()
    client._session.request.return_value = resp

    result = await client._request("POST", "/me/player/next")

    assert result is None


async def test_request_200_empty_content_type_returns_none():
    """200 with empty content-type (no JSON body) must return None, not raise."""
    client = _make_client()
    resp = _mock_response(200, "", body="")
    client._session = MagicMock()
    client._session.request.return_value = resp

    result = await client._request("POST", "/me/player/next")

    assert result is None


async def test_request_200_json_content_type_returns_parsed():
    """200 with application/json must parse and return the body."""
    import json

    client = _make_client()
    resp = _mock_response(200, "application/json")
    resp.json = AsyncMock(return_value={"tracks": {"items": []}})
    client._session = MagicMock()
    client._session.request.return_value = resp

    result = await client._request("GET", "/search", params={"q": "test"})

    assert result == {"tracks": {"items": []}}


async def test_request_non_ok_raises_spotify_error():
    """Non-2xx responses must raise SpotifyError."""
    client = _make_client()
    resp = _mock_response(404, "application/json", body="not found")
    client._session = MagicMock()
    client._session.request.return_value = resp

    with pytest.raises(SpotifyError, match="404"):
        await client._request("GET", "/me/player")
