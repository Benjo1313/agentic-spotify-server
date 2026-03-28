"""Tests for Phase 1 playback control tools.

Covers: get_queue, previous_track, set_shuffle, set_repeat, seek, recently_played
"""

from unittest.mock import AsyncMock, patch

import pytest

from bot.agent import _exec_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_track(name="Blue Train", artist="John Coltrane", uri="spotify:track:abc"):
    return {
        "name": name,
        "artists": [{"name": artist}],
        "album": {"name": name},
        "duration_ms": 240000,
        "uri": uri,
    }


def make_queue_response(current_name="Blue Train", queue_tracks=None):
    if queue_tracks is None:
        queue_tracks = [
            make_track(f"Track {i}", "Artist", f"spotify:track:{i}")
            for i in range(1, 6)
        ]
    return {
        "currently_playing": make_track(current_name),
        "queue": queue_tracks,
    }


def make_recently_played(count=5):
    return {
        "items": [
            {
                "track": make_track(f"Track {i}", f"Artist {i}", f"spotify:track:{i}"),
                "played_at": f"2026-03-27T{10+i:02d}:00:00Z",
            }
            for i in range(count)
        ]
    }


# ---------------------------------------------------------------------------
# 1a: get_queue
# ---------------------------------------------------------------------------

class TestGetQueue:
    @pytest.mark.asyncio
    async def test_get_queue_shows_currently_playing(self):
        """get_queue must include the currently playing track name."""
        spotify = AsyncMock()
        spotify.get_queue.return_value = make_queue_response(current_name="Blue Train")
        snapcast = AsyncMock()

        result = await _exec_tool("get_queue", {}, spotify, snapcast)

        assert "Blue Train" in result
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_get_queue_shows_next_tracks(self):
        """get_queue must list upcoming tracks."""
        queue = [make_track(f"Track {i}") for i in range(3)]
        spotify = AsyncMock()
        spotify.get_queue.return_value = make_queue_response(queue_tracks=queue)
        snapcast = AsyncMock()

        result = await _exec_tool("get_queue", {}, spotify, snapcast)

        assert "Track 0" in result
        assert "Track 1" in result
        assert "Track 2" in result

    @pytest.mark.asyncio
    async def test_get_queue_caps_at_ten_and_shows_truncation(self):
        """get_queue caps display at 10 tracks and notes if more exist."""
        queue = [make_track(f"Track {i}") for i in range(15)]
        spotify = AsyncMock()
        spotify.get_queue.return_value = make_queue_response(queue_tracks=queue)
        snapcast = AsyncMock()

        result = await _exec_tool("get_queue", {}, spotify, snapcast)

        # First 10 tracks shown
        assert "Track 0" in result
        assert "Track 9" in result
        # Track 10+ truncated with a note
        assert "Track 10" not in result
        assert "more" in result.lower()

    @pytest.mark.asyncio
    async def test_get_queue_empty(self):
        """get_queue handles empty queue gracefully."""
        spotify = AsyncMock()
        spotify.get_queue.return_value = {"currently_playing": make_track(), "queue": []}
        snapcast = AsyncMock()

        result = await _exec_tool("get_queue", {}, spotify, snapcast)

        assert not result.startswith("TOOL_ERROR:")
        assert "empty" in result.lower() or "nothing" in result.lower() or "Blue Train" in result


# ---------------------------------------------------------------------------
# 1b: previous_track
# ---------------------------------------------------------------------------

class TestPreviousTrack:
    @pytest.mark.asyncio
    async def test_previous_track_calls_client(self):
        """previous_track must call spotify.previous()."""
        spotify = AsyncMock()
        spotify.previous.return_value = None
        spotify.get_playback.return_value = {
            "is_playing": True,
            "item": make_track("Kind of Blue", "Miles Davis"),
            "progress_ms": 0,
        }
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            result = await _exec_tool("previous_track", {}, spotify, snapcast)

        spotify.previous.assert_called_once()
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_previous_track_returns_track_info(self):
        """previous_track handler returns post-action track name."""
        spotify = AsyncMock()
        spotify.previous.return_value = None
        spotify.get_playback.return_value = {
            "is_playing": True,
            "item": make_track("Kind of Blue", "Miles Davis"),
            "progress_ms": 0,
        }
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            result = await _exec_tool("previous_track", {}, spotify, snapcast)

        assert "Kind of Blue" in result or "Miles Davis" in result

    @pytest.mark.asyncio
    async def test_previous_track_falls_back_when_no_playback(self):
        """previous_track returns fallback when no playback state available."""
        spotify = AsyncMock()
        spotify.previous.return_value = None
        spotify.get_playback.return_value = None
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            result = await _exec_tool("previous_track", {}, spotify, snapcast)

        assert not result.startswith("TOOL_ERROR:")
        assert len(result) > 0


# ---------------------------------------------------------------------------
# 1c: set_shuffle
# ---------------------------------------------------------------------------

class TestSetShuffle:
    @pytest.mark.asyncio
    async def test_set_shuffle_on_calls_client(self):
        """set_shuffle with enabled=True calls spotify.set_shuffle(True)."""
        spotify = AsyncMock()
        spotify.set_shuffle.return_value = None
        snapcast = AsyncMock()

        result = await _exec_tool("set_shuffle", {"enabled": True}, spotify, snapcast)

        spotify.set_shuffle.assert_called_once_with(True)
        assert not result.startswith("TOOL_ERROR:")
        assert "on" in result.lower() or "enabled" in result.lower() or "shuffle" in result.lower()

    @pytest.mark.asyncio
    async def test_set_shuffle_off_calls_client(self):
        """set_shuffle with enabled=False calls spotify.set_shuffle(False)."""
        spotify = AsyncMock()
        spotify.set_shuffle.return_value = None
        snapcast = AsyncMock()

        result = await _exec_tool("set_shuffle", {"enabled": False}, spotify, snapcast)

        spotify.set_shuffle.assert_called_once_with(False)
        assert not result.startswith("TOOL_ERROR:")
        assert "off" in result.lower() or "disabled" in result.lower() or "shuffle" in result.lower()


# ---------------------------------------------------------------------------
# 1d: set_repeat
# ---------------------------------------------------------------------------

class TestSetRepeat:
    @pytest.mark.parametrize("mode", ["off", "track", "context"])
    @pytest.mark.asyncio
    async def test_set_repeat_calls_client_with_mode(self, mode):
        """set_repeat calls spotify.set_repeat() with the correct mode string."""
        spotify = AsyncMock()
        spotify.set_repeat.return_value = None
        snapcast = AsyncMock()

        result = await _exec_tool("set_repeat", {"mode": mode}, spotify, snapcast)

        spotify.set_repeat.assert_called_once_with(mode)
        assert not result.startswith("TOOL_ERROR:")


# ---------------------------------------------------------------------------
# 1e: seek
# ---------------------------------------------------------------------------

class TestSeek:
    @pytest.mark.asyncio
    async def test_seek_converts_seconds_to_ms(self):
        """seek converts position_seconds to position_ms for the client."""
        spotify = AsyncMock()
        spotify.seek.return_value = None
        snapcast = AsyncMock()

        result = await _exec_tool("seek", {"position_seconds": 90}, spotify, snapcast)

        spotify.seek.assert_called_once_with(90_000)
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_seek_zero(self):
        """seek to 0 seconds calls seek(0)."""
        spotify = AsyncMock()
        spotify.seek.return_value = None
        snapcast = AsyncMock()

        await _exec_tool("seek", {"position_seconds": 0}, spotify, snapcast)

        spotify.seek.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# 1f: recently_played
# ---------------------------------------------------------------------------

class TestRecentlyPlayed:
    @pytest.mark.asyncio
    async def test_recently_played_lists_tracks(self):
        """recently_played returns a numbered list of track — artist."""
        spotify = AsyncMock()
        spotify.get_recently_played.return_value = make_recently_played(3)
        snapcast = AsyncMock()

        result = await _exec_tool("recently_played", {}, spotify, snapcast)

        assert "Track 0" in result
        assert "Artist 0" in result
        assert "Track 2" in result
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_recently_played_empty(self):
        """recently_played handles empty history gracefully."""
        spotify = AsyncMock()
        spotify.get_recently_played.return_value = {"items": []}
        snapcast = AsyncMock()

        result = await _exec_tool("recently_played", {}, spotify, snapcast)

        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_recently_played_caps_at_ten(self):
        """recently_played shows at most 10 tracks."""
        spotify = AsyncMock()
        spotify.get_recently_played.return_value = make_recently_played(10)
        snapcast = AsyncMock()

        result = await _exec_tool("recently_played", {}, spotify, snapcast)

        lines = [l for l in result.strip().splitlines() if l.strip()]
        # header + 10 entries or just 10 entries; allow for a header line
        assert len(lines) <= 12
