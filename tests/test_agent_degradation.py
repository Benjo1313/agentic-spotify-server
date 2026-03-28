"""Tests for AI agent degradation bugs.

Covers three bugs found in bot/agent.py:
  Bug 1: Variable shadowing in get_system_status (CRITICAL)
  Bug 2: History window too large (allows LLM to answer from memory)
  Bug 3: No tool-call loop cap (infinite loop risk)
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.agent import MusicAgent, _exec_tool


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_snapcast_status(stream_id="spotify", connected_clients=2):
    return {
        "server": {
            "groups": [
                {
                    "stream_id": stream_id,
                    "clients": [
                        {"connected": True, "config": {"name": "kitchen", "volume": {"percent": 70, "muted": False}}, "host": {"name": "kitchen"}},
                        {"connected": connected_clients > 1, "config": {"name": "bedroom", "volume": {"percent": 50, "muted": False}}, "host": {"name": "bedroom"}},
                    ],
                }
            ]
        }
    }


def make_spotify_playback(is_playing=True, track_name="Blue Train", artist="John Coltrane"):
    return {
        "is_playing": is_playing,
        "item": {
            "name": track_name,
            "artists": [{"name": artist}],
            "album": {"name": "Blue Train"},
            "duration_ms": 240000,
            "uri": "spotify:track:abc123",
        },
        "progress_ms": 30000,
    }


# ---------------------------------------------------------------------------
# Bug 1: Variable shadowing in get_system_status
# ---------------------------------------------------------------------------

class TestGetSystemStatus:
    """Bug 1: `status` variable is reassigned from dict → str, causing TypeError."""

    @pytest.mark.asyncio
    async def test_get_system_status_with_active_playback(self):
        """get_system_status must not raise TypeError when a track is playing."""
        snapcast = AsyncMock()
        snapcast.get_status.return_value = make_snapcast_status()

        spotify = AsyncMock()
        spotify.get_playback.return_value = make_spotify_playback(is_playing=True)

        result = await _exec_tool("get_system_status", {}, spotify, snapcast)

        assert "TOOL_ERROR" not in result, f"Tool failed: {result}"
        assert "Blue Train" in result
        assert "John Coltrane" in result
        assert "playing" in result
        assert "spotify" in result  # stream id from snapcast group

    @pytest.mark.asyncio
    async def test_get_system_status_paused(self):
        """get_system_status correctly reports paused state."""
        snapcast = AsyncMock()
        snapcast.get_status.return_value = make_snapcast_status()

        spotify = AsyncMock()
        spotify.get_playback.return_value = make_spotify_playback(is_playing=False)

        result = await _exec_tool("get_system_status", {}, spotify, snapcast)

        assert "TOOL_ERROR" not in result
        assert "paused" in result

    @pytest.mark.asyncio
    async def test_get_system_status_nothing_playing(self):
        """get_system_status handles no active playback gracefully."""
        snapcast = AsyncMock()
        snapcast.get_status.return_value = make_snapcast_status()

        spotify = AsyncMock()
        spotify.get_playback.return_value = None

        result = await _exec_tool("get_system_status", {}, spotify, snapcast)

        assert "TOOL_ERROR" not in result
        assert "nothing playing" in result.lower()
        assert "spotify" in result  # still shows group info


# ---------------------------------------------------------------------------
# Bug 3: No tool-call loop cap
# ---------------------------------------------------------------------------

def make_llm_always_tool_calling():
    """Returns a mock LLM that always responds with a tool call (never finishes)."""
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.function.name = "now_playing"
    tool_call.function.arguments = "{}"

    msg = MagicMock()
    msg.tool_calls = [tool_call]
    msg.content = None

    choice = MagicMock()
    choice.message = msg

    response = MagicMock()
    response.choices = [choice]

    llm = AsyncMock()
    llm.chat.completions.create = AsyncMock(return_value=response)
    return llm


def make_llm_tool_then_text(tool_name="now_playing", tool_args="{}", reply="Now playing: Blue Train."):
    """Returns a mock LLM that makes one tool call, then gives a text reply."""
    # First call: tool call
    tool_call = MagicMock()
    tool_call.id = "call_456"
    tool_call.function.name = tool_name
    tool_call.function.arguments = tool_args

    tool_msg = MagicMock()
    tool_msg.tool_calls = [tool_call]
    tool_msg.content = None

    tool_choice = MagicMock()
    tool_choice.message = tool_msg

    tool_response = MagicMock()
    tool_response.choices = [tool_choice]

    # Second call: text reply
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


class TestLoopCap:
    """Bug 3: while True loop must be capped to prevent infinite spin."""

    @pytest.mark.asyncio
    async def test_run_caps_tool_rounds(self):
        """Agent must return a fallback message after 10 tool rounds, not loop forever."""
        spotify = AsyncMock()
        spotify.get_playback.return_value = make_spotify_playback()

        snapcast = AsyncMock()

        llm = make_llm_always_tool_calling()
        agent = MusicAgent(spotify, snapcast, llm, model="deepseek-chat")

        result = await agent.run("what's playing?")

        # Must return something (not hang), and it should be a string
        assert isinstance(result, str)
        assert len(result) > 0
        # LLM should have been called at most 10 times
        assert llm.chat.completions.create.call_count <= 10

    @pytest.mark.asyncio
    async def test_run_normal_flow_with_cap(self):
        """Normal tool-then-text flow still works correctly with the loop cap."""
        spotify = AsyncMock()
        spotify.get_playback.return_value = make_spotify_playback()

        snapcast = AsyncMock()

        llm = make_llm_tool_then_text(reply="Now playing: Blue Train by John Coltrane.")
        agent = MusicAgent(spotify, snapcast, llm, model="deepseek-chat")

        result = await agent.run("what's playing?")

        assert result == "Now playing: Blue Train by John Coltrane."
        assert llm.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# Bug 2: History window too large
# ---------------------------------------------------------------------------

class TestHistoryWindow:
    """Bug 2: History window must be bounded to 6 (3 exchanges)."""

    @pytest.mark.asyncio
    async def test_history_bounded_to_six(self):
        """After many messages, _history must not exceed 6 entries."""
        spotify = AsyncMock()
        snapcast = AsyncMock()

        # LLM always returns a simple text reply (no tool calls)
        def make_text_reply(content):
            msg = MagicMock()
            msg.tool_calls = None
            msg.content = content
            choice = MagicMock()
            choice.message = msg
            response = MagicMock()
            response.choices = [choice]
            return response

        responses = [make_text_reply(f"Reply {i}") for i in range(10)]
        llm = AsyncMock()
        llm.chat.completions.create = AsyncMock(side_effect=responses)

        agent = MusicAgent(spotify, snapcast, llm, model="deepseek-chat")

        for i in range(5):
            await agent.run(f"Message {i}")

        assert len(agent._history) <= 6, (
            f"History grew to {len(agent._history)} entries, expected <= 6"
        )
