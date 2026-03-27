"""AI music agent with tool-use loop.

Accepts natural language commands and executes Spotify/Snapcast operations.

CLI usage:
    python -m bot.agent "play Blue Train by Coltrane"
    python -m bot.agent "mute the kitchen"
    python -m bot.agent "what's playing?"
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from openai import OpenAI

from bot.snapcast_client import SnapcastClient, SnapcastError
from bot.spotify_client import SpotifyClient, SpotifyError


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_tracks",
            "description": "Search for tracks on Spotify. Returns up to 5 results with track name, artist, and URI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query, e.g. 'Blue Train Coltrane'"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_track",
            "description": "Play a specific Spotify track by URI, or resume playback if no URI given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "uri": {"type": "string", "description": "Spotify track URI e.g. 'spotify:track:xxx'. Omit to resume."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pause_playback",
            "description": "Pause the currently playing track.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skip_track",
            "description": "Skip to the next track in the queue.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_queue",
            "description": "Add a track to the end of the playback queue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "uri": {"type": "string", "description": "Spotify track URI to queue."},
                },
                "required": ["uri"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "now_playing",
            "description": "Get the currently playing track, artist, album, and progress.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_rooms",
            "description": "List all audio nodes/rooms with volume, mute status, and connection state.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set volume (0-100) for a specific room.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room": {"type": "string", "description": "Room name, e.g. 'kitchen'. Case-insensitive."},
                    "volume": {"type": "integer", "minimum": 0, "maximum": 100},
                },
                "required": ["room", "volume"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mute_room",
            "description": "Mute a specific room.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room": {"type": "string", "description": "Room name to mute."},
                },
                "required": ["room"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unmute_room",
            "description": "Unmute a previously muted room.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room": {"type": "string", "description": "Room name to unmute."},
                },
                "required": ["room"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Full system status: what's playing, rooms connected, volumes, and active streams.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "help",
            "description": "Show examples of what the user can ask. Use when the user seems confused.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

SYSTEM_PROMPT = """You are a music server assistant controlling a multi-room audio system.
You have tools to control Spotify playback and manage room volumes via Snapcast.

Rules:
- When asked to play something, always search first, then play the best match.
- Keep responses short and conversational — one or two sentences max.
- If a tool call fails, explain what went wrong simply.
- Room names map to Snapcast clients. If a room isn't found, list available rooms.
- Never mention technical details like URIs, client IDs, or API errors to the user."""


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def _exec_tool(name: str, args: dict, spotify: SpotifyClient, snapcast: SnapcastClient) -> str:
    try:
        if name == "search_tracks":
            tracks = await spotify.search(args["query"], limit=5)
            if not tracks:
                return "No tracks found."
            lines = [f'{t["name"]} — {t["artists"][0]["name"]} | {t["uri"]}' for t in tracks]
            return "\n".join(lines)

        elif name == "play_track":
            uri = args.get("uri")
            if uri:
                await spotify.play(uris=[uri])
                return f"Playing {uri}"
            else:
                await spotify.play()
                return "Resumed playback."

        elif name == "pause_playback":
            await spotify.pause()
            return "Paused."

        elif name == "skip_track":
            await spotify.skip()
            return "Skipped."

        elif name == "add_to_queue":
            await spotify.add_to_queue(args["uri"])
            return f"Added to queue: {args['uri']}"

        elif name == "now_playing":
            state = await spotify.get_playback()
            if not state or not state.get("item"):
                return "Nothing is currently playing."
            item = state["item"]
            artist = item["artists"][0]["name"]
            progress_ms = state.get("progress_ms", 0)
            duration_ms = item["duration_ms"]
            progress = f"{progress_ms // 60000}:{(progress_ms % 60000) // 1000:02d}"
            duration = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
            return f'{item["name"]} — {artist} | {item["album"]["name"]} | {progress}/{duration}'

        elif name == "list_rooms":
            clients = await snapcast.get_clients()
            if not clients:
                return "No rooms found."
            lines = []
            for c in clients:
                name_ = c["config"]["name"] or c["host"]["name"]
                vol = c["config"]["volume"]["percent"]
                muted = c["config"]["volume"]["muted"]
                connected = c["connected"]
                lines.append(f'{name_}: vol={vol} muted={muted} connected={connected}')
            return "\n".join(lines)

        elif name == "set_volume":
            client_id = await snapcast.resolve_client(args["room"])
            await snapcast.set_volume(client_id, args["volume"])
            return f"Set {args['room']} volume to {args['volume']}."

        elif name == "mute_room":
            client_id = await snapcast.resolve_client(args["room"])
            await snapcast.set_mute(client_id, True)
            return f"Muted {args['room']}."

        elif name == "unmute_room":
            client_id = await snapcast.resolve_client(args["room"])
            await snapcast.set_mute(client_id, False)
            return f"Unmuted {args['room']}."

        elif name == "get_system_status":
            status = await snapcast.get_status()
            playback = await spotify.get_playback()

            lines = []
            if playback and playback.get("item"):
                item = playback["item"]
                lines.append(f'Now playing: {item["name"]} — {item["artists"][0]["name"]}')
            else:
                lines.append("Spotify: nothing playing")

            for group in status["server"]["groups"]:
                stream = group["stream_id"]
                connected = [c for c in group["clients"] if c["connected"]]
                lines.append(f'Group stream={stream} connected_clients={len(connected)}')

            return "\n".join(lines)

        elif name == "help":
            return (
                "You can ask me things like:\n"
                "- 'play Bohemian Rhapsody'\n"
                "- 'pause the music'\n"
                "- 'skip this song'\n"
                "- 'what's playing?'\n"
                "- 'set kitchen volume to 50'\n"
                "- 'mute the bedroom'\n"
                "- 'show all rooms'\n"
                "- 'system status'"
            )

        else:
            return f"Unknown tool: {name}"

    except (SpotifyError, SnapcastError) as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

class MusicAgent:
    def __init__(self, spotify: SpotifyClient, snapcast: SnapcastClient, llm: OpenAI, model: str):
        self._spotify = spotify
        self._snapcast = snapcast
        self._llm = llm
        self._model = model
        self._history: list[dict] = []

    async def run(self, user_message: str) -> str:
        self._history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self._history[-20:]

        while True:
            response = self._llm.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            if msg.tool_calls:
                messages.append(msg)
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    log.info("tool_call name=%s args=%s", tc.function.name, args)
                    result = await _exec_tool(tc.function.name, args, self._spotify, self._snapcast)
                    log.info("tool_result name=%s result=%r", tc.function.name, result[:200] if len(result) > 200 else result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                reply = msg.content or ""
                self._history.append({"role": "assistant", "content": reply})
                # Keep history bounded to last 10 exchanges
                if len(self._history) > 20:
                    self._history = self._history[-20:]
                return reply


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_env(path: str) -> dict:
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"')
    return env


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main():
    if len(sys.argv) < 2:
        print("Usage: python -m bot.agent \"your command here\"")
        sys.exit(1)

    user_input = " ".join(sys.argv[1:])

    env_path = Path(__file__).parent.parent / "config" / ".env"
    env = load_env(str(env_path))

    llm = OpenAI(
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
            reply = await agent.run(user_input)
            print(reply)


if __name__ == "__main__":
    asyncio.run(main())
