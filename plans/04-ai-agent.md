# Phase 4: AI Agent with Tool-Use

> **Status:** Not started
> **Dependencies:** 03-api-clients.md (Spotify and Snapcast clients must exist)
> **Parallelizable with:** Nothing — this wraps the API clients

## Overview

Build the AI agent that accepts natural language input and calls the correct Spotify/Snapcast tools. This phase delivers a CLI-testable agent — Discord integration comes in Phase 5.

---

## Tasks

1. Install AI SDK: `pip install openai`
2. Define tool schemas (see Tool Definitions below)
3. Build the agent module (`bot/agent.py`):
   - System prompt defining the agent's role and available tools
   - Tool execution loop: LLM returns tool calls -> execute -> return results -> LLM responds
   - Error handling: return error message to LLM for graceful response
   - Include current playback state in system prompt for context
4. Configure the LLM provider:
   ```python
   client = OpenAI(
       api_key=os.environ["DEEPSEEK_API_KEY"],
       base_url="https://api.deepseek.com"
   )
   model = "deepseek-chat"
   ```
5. Build a CLI test harness:
   ```bash
   python -m bot.agent "play Blue Train by Coltrane"
   python -m bot.agent "mute the kitchen"
   python -m bot.agent "what's playing?"
   ```
6. Test all tool combinations
7. Add conversation memory (last 10 messages) for contextual follow-ups

---

## Done Criteria

- [ ] Agent correctly interprets natural language commands
- [ ] All 12 tools work via CLI
- [ ] Agent handles errors gracefully (e.g., "I couldn't find that song")
- [ ] Conversation memory works for follow-ups ("play jazz" -> "actually, play Miles Davis")
- [ ] CLI test harness works end-to-end

---

## Tool Definitions

12 tools total, OpenAI function calling format (compatible with DeepSeek and Qwen).

### Spotify Tools

```json
{
  "name": "search_tracks",
  "description": "Search for tracks on Spotify or in the local music library. Returns up to 5 results with track name, artist, album, and URI.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search query, e.g. 'Blue Train Coltrane' or 'jazz piano'"
      },
      "source": {
        "type": "string",
        "enum": ["spotify", "local", "all"],
        "description": "Where to search. Defaults to 'all'."
      }
    },
    "required": ["query"]
  }
}
```

```json
{
  "name": "play_track",
  "description": "Play a specific track by URI, or resume playback if no URI is provided.",
  "parameters": {
    "type": "object",
    "properties": {
      "uri": {
        "type": "string",
        "description": "Track URI (e.g. 'spotify:track:xxx' or 'local:track:xxx'). If omitted, resumes current playback."
      }
    },
    "required": []
  }
}
```

```json
{
  "name": "pause_playback",
  "description": "Pause the currently playing track.",
  "parameters": { "type": "object", "properties": {}, "required": [] }
}
```

```json
{
  "name": "skip_track",
  "description": "Skip to the next track in the queue.",
  "parameters": { "type": "object", "properties": {}, "required": [] }
}
```

```json
{
  "name": "add_to_queue",
  "description": "Add a track to the end of the playback queue.",
  "parameters": {
    "type": "object",
    "properties": {
      "uri": {
        "type": "string",
        "description": "Track URI to add to the queue."
      }
    },
    "required": ["uri"]
  }
}
```

```json
{
  "name": "now_playing",
  "description": "Get information about the currently playing track, including track name, artist, album, progress, and duration.",
  "parameters": { "type": "object", "properties": {}, "required": [] }
}
```

### Snapcast Tools

```json
{
  "name": "list_rooms",
  "description": "List all connected audio nodes/rooms with their current volume, mute status, and connection state.",
  "parameters": { "type": "object", "properties": {}, "required": [] }
}
```

```json
{
  "name": "set_volume",
  "description": "Set the volume for a specific room/node. Volume is 0-100.",
  "parameters": {
    "type": "object",
    "properties": {
      "room": {
        "type": "string",
        "description": "Room name, e.g. 'kitchen', 'living room'. Case-insensitive, supports partial matches."
      },
      "volume": {
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "description": "Volume level (0-100)."
      }
    },
    "required": ["room", "volume"]
  }
}
```

```json
{
  "name": "mute_room",
  "description": "Mute a specific room/node.",
  "parameters": {
    "type": "object",
    "properties": {
      "room": { "type": "string", "description": "Room name to mute." }
    },
    "required": ["room"]
  }
}
```

```json
{
  "name": "unmute_room",
  "description": "Unmute a previously muted room/node, restoring it to its previous volume.",
  "parameters": {
    "type": "object",
    "properties": {
      "room": { "type": "string", "description": "Room name to unmute." }
    },
    "required": ["room"]
  }
}
```

```json
{
  "name": "get_system_status",
  "description": "Get full system status: what's playing, which rooms are connected, volume levels, and which stream each room is listening to.",
  "parameters": { "type": "object", "properties": {}, "required": [] }
}
```

### System Tools

```json
{
  "name": "help",
  "description": "Show examples of what the user can ask. Use when the user seems confused or asks for help.",
  "parameters": { "type": "object", "properties": {}, "required": [] }
}
```

---

## Technical Notes

- **Framework:** Raw `openai` library with function calling (~50 lines for the tool-use loop). No LangChain.
- **Model:** DeepSeek Chat (OpenAI-compatible, cheap, good function calling). Swappable to Qwen by changing `base_url` and `model`.
- **Memory:** Simple list of last 10 messages. No vector store needed.
- **Validation:** Validate all tool parameters before execution. Return clear errors for invalid inputs.
