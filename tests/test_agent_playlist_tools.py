"""Tests for Phase 2 playlist and search tools.

Covers: search (renamed from search_tracks, with type param), list_playlists,
        get_playlist_tracks, play_playlist, play_album
"""

from unittest.mock import AsyncMock, call, patch

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


def make_album(name="Kind of Blue", artist="Miles Davis", uri="spotify:album:x"):
    return {
        "name": name,
        "artists": [{"name": artist}],
        "uri": uri,
    }


def make_playlist(name="Chill Vibes", owner="testuser", total=42, uri="spotify:playlist:p1"):
    return {
        "name": name,
        "owner": {"display_name": owner},
        "tracks": {"total": total},
        "uri": uri,
        "id": uri.split(":")[-1],
    }


def make_artist(name="Miles Davis", followers=500_000, uri="spotify:artist:a1"):
    return {
        "name": name,
        "followers": {"total": followers},
        "uri": uri,
    }


# ---------------------------------------------------------------------------
# 2a: search (renamed from search_tracks, with type param)
# ---------------------------------------------------------------------------

class TestSearch:
    @pytest.mark.asyncio
    async def test_search_track_default_type(self):
        """search without type param defaults to 'track'."""
        spotify = AsyncMock()
        spotify.search.return_value = [make_track("Blue Train", "John Coltrane")]
        snapcast = AsyncMock()

        result = await _exec_tool("search", {"query": "Blue Train"}, spotify, snapcast)

        spotify.search.assert_called_once_with("Blue Train", type="track", limit=5)
        assert "Blue Train" in result
        assert "John Coltrane" in result
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_search_album_type(self):
        """search with type='album' formats album results."""
        spotify = AsyncMock()
        spotify.search.return_value = [make_album("Kind of Blue", "Miles Davis")]
        snapcast = AsyncMock()

        result = await _exec_tool("search", {"query": "Kind of Blue", "type": "album"}, spotify, snapcast)

        spotify.search.assert_called_once_with("Kind of Blue", type="album", limit=5)
        assert "Kind of Blue" in result
        assert "Miles Davis" in result

    @pytest.mark.asyncio
    async def test_search_playlist_type(self):
        """search with type='playlist' formats playlist results."""
        spotify = AsyncMock()
        spotify.search.return_value = [make_playlist("Chill Vibes", "testuser", 42)]
        snapcast = AsyncMock()

        result = await _exec_tool("search", {"query": "Chill Vibes", "type": "playlist"}, spotify, snapcast)

        assert "Chill Vibes" in result
        assert "42" in result  # track count

    @pytest.mark.asyncio
    async def test_search_artist_type(self):
        """search with type='artist' formats artist results."""
        spotify = AsyncMock()
        spotify.search.return_value = [make_artist("Miles Davis", 500_000)]
        snapcast = AsyncMock()

        result = await _exec_tool("search", {"query": "Miles Davis", "type": "artist"}, spotify, snapcast)

        assert "Miles Davis" in result

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """search returns a no-results message when empty."""
        spotify = AsyncMock()
        spotify.search.return_value = []
        snapcast = AsyncMock()

        result = await _exec_tool("search", {"query": "xyznotfound"}, spotify, snapcast)

        assert "No" in result or "not found" in result.lower()
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_search_tracks_old_name_unknown(self):
        """search_tracks (old name) no longer works — returns Unknown tool."""
        spotify = AsyncMock()
        snapcast = AsyncMock()

        result = await _exec_tool("search_tracks", {"query": "something"}, spotify, snapcast)

        assert "Unknown tool" in result


# ---------------------------------------------------------------------------
# 2b: list_playlists
# ---------------------------------------------------------------------------

class TestListPlaylists:
    @pytest.mark.asyncio
    async def test_list_playlists_shows_names(self):
        """list_playlists returns a numbered list of playlist names."""
        spotify = AsyncMock()
        spotify.get_playlists.return_value = {
            "items": [
                make_playlist("Chill Vibes", "me", 42),
                make_playlist("Jazz Classics", "me", 17),
            ]
        }
        snapcast = AsyncMock()

        result = await _exec_tool("list_playlists", {}, spotify, snapcast)

        assert "Chill Vibes" in result
        assert "Jazz Classics" in result
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_list_playlists_shows_track_count(self):
        """list_playlists includes the track count for each playlist."""
        spotify = AsyncMock()
        spotify.get_playlists.return_value = {
            "items": [make_playlist("My Playlist", "me", 99)]
        }
        snapcast = AsyncMock()

        result = await _exec_tool("list_playlists", {}, spotify, snapcast)

        assert "99" in result

    @pytest.mark.asyncio
    async def test_list_playlists_empty(self):
        """list_playlists handles empty playlist library gracefully."""
        spotify = AsyncMock()
        spotify.get_playlists.return_value = {"items": []}
        snapcast = AsyncMock()

        result = await _exec_tool("list_playlists", {}, spotify, snapcast)

        assert not result.startswith("TOOL_ERROR:")


# ---------------------------------------------------------------------------
# 2c: get_playlist_tracks
# ---------------------------------------------------------------------------

class TestGetPlaylistTracks:
    @pytest.mark.asyncio
    async def test_get_playlist_tracks_lists_tracks(self):
        """get_playlist_tracks returns numbered track list."""
        spotify = AsyncMock()
        spotify.get_playlist_tracks.return_value = {
            "items": [
                {"track": make_track("So What", "Miles Davis")},
                {"track": make_track("Freddie Freeloader", "Miles Davis")},
            ],
            "total": 2,
        }
        snapcast = AsyncMock()

        result = await _exec_tool("get_playlist_tracks", {"playlist_id": "abc123"}, spotify, snapcast)

        spotify.get_playlist_tracks.assert_called_once_with("abc123", limit=20)
        assert "So What" in result
        assert "Freddie Freeloader" in result
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_get_playlist_tracks_shows_total(self):
        """get_playlist_tracks shows total track count when truncated."""
        items = [{"track": make_track(f"Track {i}")} for i in range(20)]
        spotify = AsyncMock()
        spotify.get_playlist_tracks.return_value = {"items": items, "total": 47}
        snapcast = AsyncMock()

        result = await _exec_tool("get_playlist_tracks", {"playlist_id": "abc123"}, spotify, snapcast)

        assert "47" in result  # total shown


# ---------------------------------------------------------------------------
# 2d: play_playlist
# ---------------------------------------------------------------------------

class TestPlayPlaylist:
    @pytest.mark.asyncio
    async def test_play_playlist_plays_context_uri(self):
        """play_playlist calls spotify.play with context_uri."""
        spotify = AsyncMock()
        spotify.play.return_value = None
        snapcast = AsyncMock()

        result = await _exec_tool("play_playlist", {"playlist_id": "pl123"}, spotify, snapcast)

        spotify.play.assert_called_once_with(context_uri="spotify:playlist:pl123")
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_play_playlist_with_shuffle_enables_shuffle_first(self):
        """play_playlist with shuffle=True enables shuffle before playing."""
        spotify = AsyncMock()
        spotify.set_shuffle.return_value = None
        spotify.play.return_value = None
        snapcast = AsyncMock()

        result = await _exec_tool("play_playlist", {"playlist_id": "pl123", "shuffle": True}, spotify, snapcast)

        spotify.set_shuffle.assert_called_once_with(True)
        spotify.play.assert_called_once_with(context_uri="spotify:playlist:pl123")
        assert not result.startswith("TOOL_ERROR:")

    @pytest.mark.asyncio
    async def test_play_playlist_without_shuffle_does_not_set_shuffle(self):
        """play_playlist with shuffle=False does not call set_shuffle."""
        spotify = AsyncMock()
        spotify.play.return_value = None
        snapcast = AsyncMock()

        await _exec_tool("play_playlist", {"playlist_id": "pl123", "shuffle": False}, spotify, snapcast)

        spotify.set_shuffle.assert_not_called()


# ---------------------------------------------------------------------------
# 2e: play_album
# ---------------------------------------------------------------------------

class TestPlayAlbum:
    @pytest.mark.asyncio
    async def test_play_album_plays_context_uri(self):
        """play_album calls spotify.play with the album URI as context_uri."""
        spotify = AsyncMock()
        spotify.play.return_value = None
        snapcast = AsyncMock()

        result = await _exec_tool(
            "play_album", {"album_uri": "spotify:album:abc"}, spotify, snapcast
        )

        spotify.play.assert_called_once_with(context_uri="spotify:album:abc")
        assert not result.startswith("TOOL_ERROR:")
