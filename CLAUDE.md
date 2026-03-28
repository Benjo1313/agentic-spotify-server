# Agentic Spotify Server

Multi-room music server with AI-powered Discord control. Spotify audio streams through librespot → Snapcast to synchronized clients across the LAN.

## Tech Stack

- **Python 3** — bot, agent, API clients
- **discord.py v2** — Discord integration (async)
- **OpenAI SDK** → DeepSeek API — AI agent with function calling
- **aiohttp** — async HTTP for Spotify Web API
- **requests** — sync HTTP for Snapcast JSON-RPC (wrapped in `asyncio.to_thread`)
- **librespot v0.8.0** — Spotify Connect receiver (compiled from source, pipe backend)
- **Snapcast v0.35.0** — synchronized multi-room audio distribution
- **Mopidy** — secondary music source for local files

## Project Structure

```
bot/
  agent.py          — AI tool-use loop (DeepSeek LLM, TOOLS schema, MusicAgent class)
  discord_bot.py    — Discord listener, routes messages through MusicAgent
  spotify_client.py — Spotify Web API client (OAuth2 token refresh, playback control)
  snapcast_client.py— Snapcast JSON-RPC client (rooms, volumes, mute/unmute)
config/
  .env              — secrets (gitignored)
  .env.example      — template for required env vars
scripts/
  spotify_auth.py   — one-time OAuth2 flow to obtain Spotify refresh token
  setup-linux-node.sh   — install + configure snapclient on Linux
  setup-macos-node.sh   — install + configure snapclient on macOS (Homebrew + launchd)
  setup-windows-node.ps1— install + configure snapclient on Windows (winget + Task Scheduler)
plans/              — architecture docs and implementation plans
```

## Environment Variables (config/.env)

| Variable | Purpose |
|----------|---------|
| `SPOTIFY_CLIENT_ID` | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret |
| `SPOTIFY_REFRESH_TOKEN` | Obtained via `scripts/spotify_auth.py` |
| `DISCORD_BOT_TOKEN` | Discord bot token |
| `DEEPSEEK_API_KEY` | DeepSeek API key (OpenAI-compatible) |
| `DISCORD_MUSIC_CHANNEL` | Channel name the bot listens in (default: `spotify-chat`) |

## Running

```bash
# One-time: obtain Spotify refresh token
python scripts/spotify_auth.py

# Start the Discord bot (runs the AI agent)
python -m bot.discord_bot

# CLI mode (no Discord)
python -m bot.agent "play Blue Train by Coltrane"
```

## Server Infrastructure (Linux machine: 192.168.0.127)

### Services

| Service | Port | Config |
|---------|------|--------|
| snapserver | 1704 (audio), 1780 (HTTP/JSON-RPC) | `/etc/snapserver.conf` |
| snapclient (local) | — | `/etc/default/snapclient` |
| librespot v0.8.0 | — | managed by snapserver (process stream) |
| mopidy | 6680 | `/etc/mopidy/mopidy.conf` |

### Audio Pipeline

```
Spotify (320 kbps OGG Vorbis)
  → librespot (decodes to 44100:16:2 PCM)
    → snapserver (encodes to FLAC, lossless)
      → snapclients (decode FLAC → system audio)
```

- librespot binary: `/usr/local/bin/librespot` (v0.8.0, compiled from source with `native-tls,with-libmdns`)
- librespot credentials: `/var/lib/snapserver/librespot/credentials.json` (owned by `snapserver` user)
- snapserver runs as systemd service under user `snapserver`
- librespot auth uses Spotify Connect zeroconf (SSO-compatible, no password)

### Adding a Node

```bash
# Linux
bash scripts/setup-linux-node.sh --server 192.168.0.127 --name "kitchen"

# macOS
bash scripts/setup-macos-node.sh --server 192.168.0.127 --name "bedroom"

# Windows (PowerShell as Admin)
.\scripts\setup-windows-node.ps1 -Server 192.168.0.127 -Name "office"
```

## Conventions

- The AI agent uses DeepSeek via the OpenAI SDK (`base_url="https://api.deepseek.com"`)
- Snapcast client uses `requests` (sync) instead of `aiohttp` because snapserver sends `Connection: close` headers that aiohttp's strict parser rejects
- Client name resolution is fuzzy-matched (SequenceMatcher, threshold 0.6)
- Discord rate limit: 2 seconds between commands per user

## AI Agent Behaviour Notes

- **Always fetch fresh state via tools** — the agent keeps a rolling 6-message history (3 exchanges). Without an explicit instruction, the LLM will answer state questions (e.g. "what's playing?") from its prior responses in history rather than calling the tool again. The system prompt contains a rule enforcing a fresh tool call for any current-state query. If the bot starts giving stale answers, check that rule is still present in `SYSTEM_PROMPT` in `bot/agent.py`.
- **History window is 6, not larger** — a 20-message window caused DeepSeek to answer state queries from stale "now playing" replies in context instead of calling tools. 6 messages (3 exchanges) is enough for multi-step flows (search → play) while keeping context fresh.
- **Tool-call loop is capped at 10 rounds** — `run()` uses `for _round in range(10)` instead of `while True`. An uncapped loop caused unbounded memory growth (7+ GB) when the LLM kept returning tool calls without a text reply, eventually triggering the OOM killer.
- **`get_system_status` uses `play_state` variable, not `status`** — the snapcast status dict is stored in `status`; the playback string (`"playing"` / `"paused"`) is stored separately in `play_state`. Reusing `status` shadowed the dict and caused `TypeError: string indices must be integers` on every call during active playback.
- **`now_playing` includes play/pause status** — the Spotify `/me/player` response includes an `is_playing` boolean. The `now_playing` and `get_system_status` tool handlers surface this as `playing` or `paused` in their return string so the LLM can correctly report playback state.

## Testing

No test suite yet.
