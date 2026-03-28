"""Tests for async LLM client usage in MusicAgent (Bug 3)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.agent import MusicAgent
from bot.snapcast_client import SnapcastClient
from bot.spotify_client import SpotifyClient


def _mock_response(content: str):
    """Build a minimal ChatCompletion-like mock with no tool calls."""
    message = MagicMock()
    message.tool_calls = None
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


async def test_agent_run_awaits_llm():
    """MusicAgent.run must await the LLM call (AsyncMock raises TypeError if not awaited)."""
    llm = MagicMock()
    llm.chat = MagicMock()
    llm.chat.completions = MagicMock()
    llm.chat.completions.create = AsyncMock(return_value=_mock_response("ok"))

    agent = MusicAgent(
        spotify=AsyncMock(spec=SpotifyClient),
        snapcast=AsyncMock(spec=SnapcastClient),
        llm=llm,
        model="test-model",
    )

    reply = await agent.run("hi")

    assert reply == "ok"
    llm.chat.completions.create.assert_awaited_once()
