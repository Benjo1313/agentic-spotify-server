"""Discord bot that wraps the AI music agent.

Listens to messages in Discord and routes them through the AI agent
to control Spotify playback and Snapcast room volumes.

Usage:
    python -m bot.discord_bot
"""

import asyncio
import logging
import time
from pathlib import Path

import discord

from bot.agent import MusicAgent, load_env
from bot.snapcast_client import SnapcastClient
from bot.spotify_client import SpotifyClient
from openai import AsyncOpenAI


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HELP_TEXT = """**Music Server Commands** — just type naturally, or use these examples:
- `Play Blue Train by Coltrane`
- `Skip this song`
- `What's playing?`
- `Pause the music`
- `Queue up something by Miles Davis`
- `Mute the kitchen`
- `Set living room volume to 50`
- `List all rooms`
- `System status`

Type `!help` anytime to see this again."""

RATE_LIMIT_SECONDS = 2


class MusicBot(discord.Client):
    def __init__(self, agent: MusicAgent, music_channel: str):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._agent = agent
        self._music_channel = music_channel
        self._last_request: dict[int, float] = {}  # user_id -> timestamp

    async def on_ready(self):
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)
        await self._health_check()

    async def _health_check(self):
        """Ping Snapcast and Spotify on startup; log warnings if unreachable."""
        try:
            await self._agent._snapcast.get_status()
            log.info("health_check snapcast=ok")
        except Exception as e:
            log.warning("health_check snapcast=UNREACHABLE error=%s", e)

        try:
            await self._agent._spotify.get_playback()
            log.info("health_check spotify=ok")
        except Exception as e:
            log.warning("health_check spotify=UNREACHABLE error=%s", e)

    async def on_message(self, message: discord.Message):
        # Ignore bots (including self)
        if message.author.bot:
            return

        in_music_channel = message.channel.name == self._music_channel
        mentioned = self.user in message.mentions

        # Only respond in the music channel or when mentioned
        if not in_music_channel and not mentioned:
            return

        # Strip the mention before passing to the agent
        content = message.content.strip()
        if mentioned:
            content = content.replace(f"<@{self.user.id}>", "").replace(f"<@!{self.user.id}>", "").strip()

        if not content:
            await message.channel.send(HELP_TEXT)
            return

        # Non-AI help escape hatch
        if content.lower() in ("!help", "help", "?"):
            await message.channel.send(HELP_TEXT)
            return

        # Rate limiting
        user_id = message.author.id
        now = time.monotonic()
        last = self._last_request.get(user_id, 0.0)
        if now - last < RATE_LIMIT_SECONDS:
            remaining = RATE_LIMIT_SECONDS - (now - last)
            await message.channel.send(
                f"Please wait {remaining:.1f}s before sending another command.",
                delete_after=3,
            )
            return
        self._last_request[user_id] = now

        # Process with AI agent
        async with message.channel.typing():
            try:
                reply = await self._agent.run(content)
            except Exception as e:
                log.exception("Agent error for message: %s", content)
                reply = "Something went wrong processing your request. Try again in a moment."

        await message.channel.send(reply)


async def main():
    env_path = Path(__file__).parent.parent / "config" / ".env"
    env = load_env(str(env_path))

    llm = AsyncOpenAI(
        api_key=env["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )

    async with SpotifyClient(
        env["SPOTIFY_CLIENT_ID"],
        env["SPOTIFY_CLIENT_SECRET"],
        env["SPOTIFY_REFRESH_TOKEN"],
    ) as spotify:
        async with SnapcastClient() as snapcast:
            agent = MusicAgent(spotify, snapcast, llm, model="deepseek-chat")
            music_channel = env.get("DISCORD_MUSIC_CHANNEL", "spotify-chat")
            bot = MusicBot(agent, music_channel)
            await bot.start(env["DISCORD_BOT_TOKEN"])


if __name__ == "__main__":
    asyncio.run(main())
