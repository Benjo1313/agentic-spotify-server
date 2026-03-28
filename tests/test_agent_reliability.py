"""Tests for Phase 0 reliability fixes.

Covers:
  Fix 0a: tool_choice="required" on round 0, "auto" on subsequent rounds
  Fix 0b: skip/play/pause handlers return post-action playback state
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.agent import MusicAgent, _exec_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_spotify_playback(track_name="Blue Train", artist="John Coltrane"):
    return {
        "is_playing": True,
        "item": {
            "name": track_name,
            "artists": [{"name": artist}],
            "album": {"name": "Blue Train"},
            "duration_ms": 240000,
            "uri": "spotify:track:abc123",
        },
        "progress_ms": 30000,
    }


def make_llm_tool_then_text(tool_name="skip_track", tool_args="{}", reply="Done."):
    """Returns a mock LLM that makes one tool call, then gives a text reply."""
    tool_call = MagicMock()
    tool_call.id = "call_456"
    tool_call.function.name = tool_name
    tool_call.function.arguments = tool_args

    tool_msg = MagicMock()
    tool_msg.tool_calls = [tool_call]
    tool_msg.content = None

    tool_choice_obj = MagicMock()
    tool_choice_obj.message = tool_msg

    tool_response = MagicMock()
    tool_response.choices = [tool_choice_obj]

    text_msg = MagicMock()
    text_msg.tool_calls = None
    text_msg.content = reply

    text_choice = MagicMock()
    text_choice.message = text_msg

    text_response = MagicMock()
    text_response.choices = [text_choice]

    llm = AsyncMock()
    llm.chat.completions.create = AsyncMock(side_effect=[tool_response, text_response])
    return llm


# ---------------------------------------------------------------------------
# Fix 0a: tool_choice on each round
# ---------------------------------------------------------------------------

class TestToolChoiceRound:
    """Fix 0a: tool_choice must be 'required' on round 0, 'auto' on round 1+."""

    @pytest.mark.asyncio
    async def test_first_round_forces_tool_call(self):
        """Round 0 must use tool_choice='required'."""
        spotify = AsyncMock()
        spotify.skip.return_value = None
        spotify.get_playback.return_value = make_spotify_playback()
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            llm = make_llm_tool_then_text(tool_name="skip_track", reply="Skipped to next track.")
            agent = MusicAgent(spotify, snapcast, llm, model="deepseek-chat")
            await agent.run("skip the song")

        call_args_list = llm.chat.completions.create.call_args_list
        assert len(call_args_list) >= 1
        first_call_kwargs = call_args_list[0].kwargs
        assert first_call_kwargs["tool_choice"] == "required"

    @pytest.mark.asyncio
    async def test_subsequent_rounds_use_auto(self):
        """Round 1+ must use tool_choice='auto'."""
        spotify = AsyncMock()
        spotify.skip.return_value = None
        spotify.get_playback.return_value = make_spotify_playback()
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            llm = make_llm_tool_then_text(tool_name="skip_track", reply="Done.")
            agent = MusicAgent(spotify, snapcast, llm, model="deepseek-chat")
            await agent.run("skip the song")

        call_args_list = llm.chat.completions.create.call_args_list
        assert len(call_args_list) >= 2
        second_call_kwargs = call_args_list[1].kwargs
        assert second_call_kwargs["tool_choice"] == "auto"


# ---------------------------------------------------------------------------
# Fix 0b: enriched action results
# ---------------------------------------------------------------------------

class TestEnrichedActionResults:
    """Fix 0b: skip, play_track, pause handlers return post-action playback state."""

    @pytest.mark.asyncio
    async def test_skip_returns_new_track_info(self):
        """skip_track handler must include post-skip track name and artist."""
        spotify = AsyncMock()
        spotify.skip.return_value = None
        spotify.get_playback.return_value = make_spotify_playback(
            track_name="A Love Supreme", artist="John Coltrane"
        )
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            result = await _exec_tool("skip_track", {}, spotify, snapcast)

        assert "A Love Supreme" in result
        assert "John Coltrane" in result

    @pytest.mark.asyncio
    async def test_skip_falls_back_when_no_playback(self):
        """skip_track returns 'Skipped.' when no playback state is available."""
        spotify = AsyncMock()
        spotify.skip.return_value = None
        spotify.get_playback.return_value = None
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            result = await _exec_tool("skip_track", {}, spotify, snapcast)

        assert result == "Skipped."

    @pytest.mark.asyncio
    async def test_play_track_returns_new_track_info(self):
        """play_track handler must include post-play track name and artist."""
        spotify = AsyncMock()
        spotify.play.return_value = None
        spotify.get_playback.return_value = make_spotify_playback(
            track_name="So What", artist="Miles Davis"
        )
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            result = await _exec_tool("play_track", {"uri": "spotify:track:xyz"}, spotify, snapcast)

        assert "So What" in result
        assert "Miles Davis" in result

    @pytest.mark.asyncio
    async def test_play_track_falls_back_when_no_playback(self):
        """play_track returns fallback string when no playback state available."""
        spotify = AsyncMock()
        spotify.play.return_value = None
        spotify.get_playback.return_value = None
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            result = await _exec_tool("play_track", {"uri": "spotify:track:xyz"}, spotify, snapcast)

        assert not result.startswith("TOOL_ERROR:")
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_play_track_resume_falls_back_when_no_playback(self):
        """play_track (resume, no URI) returns fallback when no playback state."""
        spotify = AsyncMock()
        spotify.play.return_value = None
        spotify.get_playback.return_value = None
        snapcast = AsyncMock()

        with patch("asyncio.sleep"):
            result = await _exec_tool("play_track", {}, spotify, snapcast)

        assert not result.startswith("TOOL_ERROR:")
        assert "Resumed" in result or "playing" in result.lower()

    @pytest.mark.asyncio
    async def test_pause_returns_confirmation(self):
        """pause_playback returns a non-error confirmation string."""
        spotify = AsyncMock()
        spotify.pause.return_value = None
        snapcast = AsyncMock()

        result = await _exec_tool("pause_playback", {}, spotify, snapcast)

        assert not result.startswith("TOOL_ERROR:")
        assert "Paused" in result or "paused" in result
