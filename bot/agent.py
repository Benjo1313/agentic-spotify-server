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

from openai import AsyncOpenAI

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
            "name": "search",
            "description": "Search Spotify for tracks, albums, artists, or playlists. Returns up to 5 results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query, e.g. 'Blue Train Coltrane'"},
                    "type": {
                        "type": "string",
                        "enum": ["track", "album", "artist", "playlist"],
                        "description": "What to search for. Defaults to 'track'.",
                    },
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
            "name": "get_queue",
            "description": "Show the current playback queue — what's playing and what's up next.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "previous_track",
            "description": "Go back to the previous track.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_shuffle",
            "description": "Enable or disable shuffle mode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "description": "True to enable shuffle, False to disable."},
                },
                "required": ["enabled"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_repeat",
            "description": "Set repeat mode: 'off', 'track' (repeat current song), or 'context' (repeat album/playlist).",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["off", "track", "context"],
                        "description": "Repeat mode.",
                    },
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "seek",
            "description": "Seek to a position in the current track. Position in seconds (e.g. 90 for 1:30).",
            "parameters": {
                "type": "object",
                "properties": {
                    "position_seconds": {"type": "integer", "description": "Position in seconds from the start."},
                },
                "required": ["position_seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recently_played",
            "description": "Show recently played tracks, most recent first.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_playlists",
            "description": "List the user's Spotify playlists.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_playlist_tracks",
            "description": "Get the tracks in a specific playlist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_id": {"type": "string", "description": "Spotify playlist ID."},
                },
                "required": ["playlist_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_playlist",
            "description": "Play a Spotify playlist by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "playlist_id": {"type": "string", "description": "Spotify playlist ID."},
                    "shuffle": {"type": "boolean", "description": "Enable shuffle before playing. Defaults to false."},
                },
                "required": ["playlist_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_album",
            "description": "Play a Spotify album by its URI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "album_uri": {"type": "string", "description": "Spotify album URI, e.g. 'spotify:album:xxx'."},
                },
                "required": ["album_uri"],
            },
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
- If a tool result starts with TOOL_ERROR:, always tell the user the action failed.
  Never claim success when a tool returned TOOL_ERROR:.
- Room names map to Snapcast clients. If a room isn't found, list available rooms.
- Never mention technical details like URIs, client IDs, or API errors to the user.
- ALWAYS call the appropriate tool to get current state — never answer from conversation
  history. Playback state (what's playing, paused/playing, volume) changes at any moment.
  Any question about current playback or room state requires a fresh tool call.
- NEVER respond to a playback command (play, pause, skip, previous, etc.) without calling
  the corresponding tool. If the user says "skip", you MUST call skip_track. A text-only
  reply is never acceptable for commands.
- When asked to play a playlist, search for it first (type="playlist"), then use
  play_playlist with the best match.
- When asked to play an album, search for it first (type="album"), then use play_album
  with the best match.
- For queue, playlist tracks, and search results — the tool limits output length. Tell
  the user if results are truncated.
- Seek accepts seconds. Convert timestamps like "1:30" to 90."""


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def _exec_tool(name: str, args: dict, spotify: SpotifyClient, snapcast: SnapcastClient) -> str:
    try:
        if name == "search":
            query = args["query"]
            search_type = args.get("type", "track")
            results = await spotify.search(query, type=search_type, limit=5)
            if not results:
                return f"No {search_type}s found."
            if search_type == "track":
                lines = [f'{r["name"]} — {r["artists"][0]["name"]} | {r["uri"]}' for r in results]
            elif search_type == "album":
                lines = [f'{r["name"]} — {r["artists"][0]["name"]} | {r["uri"]}' for r in results]
            elif search_type == "playlist":
                lines = [f'{r["name"]} — {r["owner"]["display_name"]} ({r["tracks"]["total"]} tracks) | {r["uri"]}' for r in results]
            elif search_type == "artist":
                lines = [f'{r["name"]} ({r["followers"]["total"]} followers) | {r["uri"]}' for r in results]
            else:
                lines = [str(r) for r in results]
            return "\n".join(lines)

        elif name == "play_track":
            uri = args.get("uri")
            if uri:
                await spotify.play(uris=[uri])
            else:
                await spotify.play()
            await asyncio.sleep(0.3)
            state = await spotify.get_playback()
            if state and state.get("item"):
                item = state["item"]
                return f'Playing: {item["name"]} — {item["artists"][0]["name"]}'
            return "Resumed playback." if not uri else f"Playing {uri}"

        elif name == "pause_playback":
            await spotify.pause()
            return "Paused."

        elif name == "skip_track":
            await spotify.skip()
            await asyncio.sleep(0.3)
            state = await spotify.get_playback()
            if state and state.get("item"):
                item = state["item"]
                return f'Skipped. Now playing: {item["name"]} — {item["artists"][0]["name"]}'
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
            status = "playing" if state.get("is_playing") else "paused"
            return f'{item["name"]} — {artist} | {item["album"]["name"]} | {progress}/{duration} | {status}'

        elif name == "get_queue":
            data = await spotify.get_queue()
            lines = []
            current = data.get("currently_playing")
            if current:
                lines.append(f'Now playing: {current["name"]} — {current["artists"][0]["name"]}')
            queue = data.get("queue", [])
            if not queue:
                lines.append("Queue is empty.")
            else:
                cap = 10
                for i, track in enumerate(queue[:cap]):
                    lines.append(f'{i + 1}. {track["name"]} — {track["artists"][0]["name"]}')
                if len(queue) > cap:
                    lines.append(f'…and {len(queue) - cap} more')
            return "\n".join(lines)

        elif name == "previous_track":
            await spotify.previous()
            await asyncio.sleep(0.3)
            state = await spotify.get_playback()
            if state and state.get("item"):
                item = state["item"]
                return f'Going back. Now playing: {item["name"]} — {item["artists"][0]["name"]}'
            return "Went back to the previous track."

        elif name == "set_shuffle":
            enabled = args["enabled"]
            await spotify.set_shuffle(enabled)
            return f'Shuffle {"on" if enabled else "off"}.'

        elif name == "set_repeat":
            mode = args["mode"]
            await spotify.set_repeat(mode)
            labels = {"off": "Repeat off.", "track": "Repeating current track.", "context": "Repeating current album/playlist."}
            return labels.get(mode, f"Repeat set to {mode}.")

        elif name == "seek":
            position_ms = args["position_seconds"] * 1000
            await spotify.seek(position_ms)
            pos = args["position_seconds"]
            return f'Seeked to {pos // 60}:{pos % 60:02d}.'

        elif name == "recently_played":
            data = await spotify.get_recently_played(limit=10)
            items = data.get("items", [])
            if not items:
                return "No recently played tracks found."
            lines = [f'{i + 1}. {item["track"]["name"]} — {item["track"]["artists"][0]["name"]}' for i, item in enumerate(items)]
            return "\n".join(lines)

        elif name == "list_playlists":
            data = await spotify.get_playlists(limit=20)
            items = data.get("items", [])
            if not items:
                return "No playlists found."
            lines = [f'{i + 1}. {p["name"]} ({p["tracks"]["total"]} tracks)' for i, p in enumerate(items)]
            return "\n".join(lines)

        elif name == "get_playlist_tracks":
            playlist_id = args["playlist_id"]
            data = await spotify.get_playlist_tracks(playlist_id, limit=20)
            items = data.get("items", [])
            total = data.get("total", len(items))
            if not items:
                return "Playlist is empty."
            lines = [f'{i + 1}. {item["track"]["name"]} — {item["track"]["artists"][0]["name"]}' for i, item in enumerate(items)]
            if total > len(items):
                lines.append(f'Showing {len(items)} of {total} tracks.')
            return "\n".join(lines)

        elif name == "play_playlist":
            playlist_id = args["playlist_id"]
            if args.get("shuffle"):
                await spotify.set_shuffle(True)
            await spotify.play(context_uri=f"spotify:playlist:{playlist_id}")
            return f"Playing playlist{' on shuffle' if args.get('shuffle') else ''}."

        elif name == "play_album":
            await spotify.play(context_uri=args["album_uri"])
            return "Playing album."

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
                play_state = "playing" if playback.get("is_playing") else "paused"
                lines.append(f'Spotify ({play_state}): {item["name"]} — {item["artists"][0]["name"]}')
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
                "- 'pause the music' / 'skip this song' / 'go back'\n"
                "- 'what's playing?' / 'what's in the queue?'\n"
                "- 'what did we listen to recently?'\n"
                "- 'shuffle on' / 'repeat this song' / 'repeat off'\n"
                "- 'skip to 1:30'\n"
                "- 'show my playlists' / 'play my Chill Vibes playlist'\n"
                "- 'play Chill Vibes on shuffle'\n"
                "- 'search for Miles Davis albums'\n"
                "- 'play the album Kind of Blue'\n"
                "- 'set kitchen volume to 50'\n"
                "- 'mute the bedroom'\n"
                "- 'show all rooms' / 'system status'"
            )

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        log.error("tool %s failed: %s", name, e)
        return f"TOOL_ERROR: {e}"


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

class MusicAgent:
    def __init__(self, spotify: SpotifyClient, snapcast: SnapcastClient, llm: AsyncOpenAI, model: str):
        self._spotify = spotify
        self._snapcast = snapcast
        self._llm = llm
        self._model = model
        self._history: list[dict] = []

    async def run(self, user_message: str) -> str:
        self._history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self._history[-6:]

        for _round in range(10):
            choice = "required" if _round == 0 else "auto"
            response = await self._llm.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOLS,
                tool_choice=choice,
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
                if len(self._history) > 6:
                    self._history = self._history[-6:]
                return reply

        return "I wasn't able to complete that after 10 attempts. Please try again."


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
            reply = await agent.run(user_input)
            print(reply)


if __name__ == "__main__":
    asyncio.run(main())
