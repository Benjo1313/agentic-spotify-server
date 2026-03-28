"""Tests for _exec_tool error handling (Bug 1)."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.agent import _exec_tool
from bot.snapcast_client import SnapcastClient, SnapcastError
from bot.spotify_client import SpotifyClient, SpotifyError


@pytest.fixture
def spotify():
    return AsyncMock(spec=SpotifyClient)


@pytest.fixture
def snapcast():
    return AsyncMock(spec=SnapcastClient)


async def test_exec_tool_skip_logs_and_prefixes_error(caplog, spotify, snapcast):
    """SpotifyError from skip must return TOOL_ERROR: prefix and log at ERROR level."""
    spotify.skip.side_effect = SpotifyError("404 no active device")

    with caplog.at_level(logging.ERROR, logger="bot.agent"):
        result = await _exec_tool("skip_track", {}, spotify, snapcast)

    assert result.startswith("TOOL_ERROR:")
    assert "404 no active device" in result
    assert any(r.levelno == logging.ERROR for r in caplog.records)


async def test_exec_tool_snapcast_error_logs_and_prefixes(caplog, spotify, snapcast):
    """SnapcastError must also return TOOL_ERROR: prefix and log at ERROR level."""
    snapcast.resolve_client.return_value = "client-1"
    snapcast.set_volume.side_effect = SnapcastError("connection refused")

    with caplog.at_level(logging.ERROR, logger="bot.agent"):
        result = await _exec_tool("set_volume", {"room": "kitchen", "volume": 50}, spotify, snapcast)

    assert result.startswith("TOOL_ERROR:")
    assert "connection refused" in result
    assert any(r.levelno == logging.ERROR for r in caplog.records)


async def test_exec_tool_unexpected_exception_caught(caplog, spotify, snapcast):
    """Unexpected exceptions (e.g. ContentTypeError) must also return TOOL_ERROR: and log."""
    from aiohttp import ContentTypeError
    from yarl import URL

    spotify.skip.side_effect = ContentTypeError(
        MagicMock(real_url=URL("https://api.spotify.com/v1/me/player/next")),
        {},
    )

    with caplog.at_level(logging.ERROR, logger="bot.agent"):
        result = await _exec_tool("skip_track", {}, spotify, snapcast)

    assert result.startswith("TOOL_ERROR:")
    assert any(r.levelno == logging.ERROR for r in caplog.records)


async def test_exec_tool_success_returns_plain_string(spotify, snapcast):
    """On success, result must NOT start with TOOL_ERROR:. With no post-skip state, returns 'Skipped.'"""
    from unittest.mock import patch

    spotify.skip.return_value = None
    spotify.get_playback.return_value = None  # no playback → simple fallback

    with patch("asyncio.sleep"):
        result = await _exec_tool("skip_track", {}, spotify, snapcast)

    assert not result.startswith("TOOL_ERROR:")
    assert result == "Skipped."
