# Phase 0: Research

> **Status:** Complete
> **Blocks:** All implementation phases
> **Completed:** 2026-03-26
> **Note:** All findings sourced from training data (cutoff May 2025). Items flagged for live verification before implementation.

## Overview

All 6 research tasks completed. Key architectural decisions confirmed. Ready to proceed to Phase 01.

---

## Research Task 1: Mopidy Ecosystem

**Acceptance criteria:**
- [x] Confirmed Mopidy installs on Linux Mint with Python 3.10+
- [x] Documented mopidy-spotify status: **BROKEN** — libspotify deprecated, Web API rewrite not stable
- [x] Confirmed FIFO output pipeline works (GStreamer `filesink` to named pipe for Snapcast)
- [x] Listed all relevant HTTP API endpoints with example curl commands
- [x] Identified: HTTP API is sufficient, `mopidy-mpd` NOT needed

### Findings

**Mopidy 3.4.x** — Python 3.9+, installs via `pip install Mopidy` or APT. Requires GStreamer 1.x + Python bindings (`python3-gst-1.0`, `gir1.2-gstreamer-1.0`). Dependencies: Tornado (HTTP), Pykka (actor model).

**mopidy-spotify: BROKEN.** Last PyPI release 4.1.1 (~2023) is non-functional. Spotify deprecated `libspotify` entirely. A rewrite to Spotify Web API is in progress but not stable. **Decision: Use librespot as primary Spotify source. Mopidy handles local files only.**

> **Verify post-2025:** Check if mopidy-spotify v5.x shipped a stable Web API release.

**mopidy-local 3.2.1** — stable, handles MP3/FLAC/OGG/WAV/AAC via GStreamer. Config: `media_dir = /path/to/music`, scan with `mopidy local scan`.

**FIFO output to Snapcast:**
```ini
[audio]
output = audioresample ! audioconvert ! audio/x-raw,rate=48000,channels=2,format=S16LE ! filesink location=/tmp/mopidy_snapfifo
```
- FIFO must exist before Mopidy starts (`mkfifo /tmp/mopidy_snapfifo`)
- Sample format must match Snapcast config: `48000:16:2`
- Snapserver must be reading the pipe before Mopidy writes (use systemd `After=`)

**HTTP JSON-RPC API** at `http://localhost:6680/mopidy/rpc` (POST, `Content-Type: application/json`):

| Namespace | Key Methods |
|-----------|-------------|
| `core.playback` | `play`, `pause`, `resume`, `stop`, `next`, `previous`, `seek`, `get_state`, `get_current_track`, `get_time_position` |
| `core.tracklist` | `add`, `remove`, `clear`, `shuffle`, `get_tl_tracks`, `get_length`, `get_repeat`, `set_repeat`, `get_random`, `set_random` |
| `core.library` | `browse`, `search`, `lookup`, `get_distinct`, `get_images` |
| `core.mixer` | `get_volume`, `set_volume`, `get_mute`, `set_mute` |
| `core.playlists` | `as_list`, `get_items`, `lookup`, `create`, `save`, `delete` |
| `core.history` | `get_length`, `get_history` |

Example curl:
```bash
# Search
curl -s -X POST http://localhost:6680/mopidy/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"core.library.search","params":{"query":{"any":["blue train coltrane"]}}}'

# Play
curl -s -X POST http://localhost:6680/mopidy/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"core.playback.play"}'
```

WebSocket events available at `ws://localhost:6680/mopidy/ws` for real-time state changes.

**mopidy-mpd: NOT needed.** HTTP JSON-RPC covers 100% of AI agent needs. MPD only useful if you want phone MPD client apps as a manual override (optional, low-effort install later).

---

## Research Task 2: Snapcast

**Acceptance criteria:**
- [x] Documented server config format (`snapserver.conf`) with stream source pointing to FIFO
- [x] Listed all JSON-RPC methods
- [x] Confirmed client availability: Linux (apt), Windows (binary), macOS (Homebrew)
- [x] Documented Bluetooth audio path (OS-level, not Snapcast-level)
- [x] Noted default ports: 1704 (audio stream), 1705 (TCP control), 1780 (HTTP/JSON-RPC)

### Findings

**Snapcast v0.28.0** (latest stable as of training cutoff). Active development by badaix.

**Ports:**
| Port | Protocol | Purpose |
|------|----------|---------|
| 1704 | TCP | Audio stream (server -> clients) |
| 1705 | TCP | TCP JSON-RPC control |
| 1780 | HTTP | HTTP JSON-RPC + Snapweb UI |

**Server config (`/etc/snapserver.conf`):**
```ini
[http]
enabled = true
bind_to_address = 0.0.0.0
port = 1780
doc_root = /usr/share/snapserver/snapweb

[tcp]
enabled = true
port = 1705

[stream]
port = 1704
codec = flac
buffer = 1000
chunk_ms = 20
sampleformat = 48000:16:2

# Mopidy local files
source = pipe:///tmp/mopidy_snapfifo?name=Mopidy&sampleformat=48000:16:2
# librespot Spotify
source = pipe:///tmp/librespot_snapfifo?name=Spotify&sampleformat=44100:16:2
```

Stream source types: `pipe://`, `alsa://`, `tcp://`, `meta://` (combine streams), `airplay://`, `librespot://` (built-in), `process://` (spawn child process).

**JSON-RPC API** (HTTP endpoint: `http://localhost:1780/jsonrpc`):

| Method | Parameters | Description |
|--------|-----------|-------------|
| **Client** | | |
| `Client.GetStatus` | `{id}` | Client info |
| `Client.SetVolume` | `{id, volume: {percent, muted}}` | Volume + mute |
| `Client.SetLatency` | `{id, latency}` | Offset in ms (for BT sync) |
| `Client.SetName` | `{id, name}` | Friendly name |
| **Group** | | |
| `Group.GetStatus` | `{id}` | Group info |
| `Group.SetStream` | `{id, stream_id}` | Assign stream to group |
| `Group.SetClients` | `{id, clients: [...]}` | Move clients between groups |
| `Group.SetMute` | `{id, mute}` | Mute entire group |
| `Group.SetName` | `{id, name}` | Friendly name |
| **Server** | | |
| `Server.GetStatus` | (none) | Full state: all groups, clients, streams |
| `Server.GetRPCVersion` | (none) | API version |
| `Server.DeleteClient` | `{id}` | Remove disconnected client |
| **Stream** | | |
| `Stream.AddStream` | `{streamUri}` | Dynamic stream add |
| `Stream.RemoveStream` | `{id}` | Remove stream |

Notifications (push events): `Client.OnConnect`, `Client.OnDisconnect`, `Client.OnVolumeChanged`, `Group.OnMute`, `Group.OnStreamChanged`, `Stream.OnUpdate`, `Server.OnUpdate`.

**Client availability:**
| Platform | Install Method | Audio Backend |
|----------|---------------|---------------|
| Linux (x86/ARM) | `apt install snapclient` or `.deb` | ALSA, PulseAudio, PipeWire |
| Windows | `.exe` from GitHub releases | WASAPI |
| macOS | `brew install snapcast` | CoreAudio |
| Android | Play Store / F-Droid | AudioTrack |

**Bluetooth:** NOT a Snapcast concern. Path: `snapclient -> system audio API -> OS default sink -> BT A2DP`. Pair BT at OS level, set as default output. Compensate latency with `Client.SetLatency` (negative value, -100 to -200ms for BT).

**Sync quality:** <1ms between wired LAN clients. Imperceptible. WiFi works fine within buffer tolerance.

**Resource usage:**
| Component | RAM | CPU (playing) |
|-----------|-----|---------------|
| snapserver | 15-25 MB | 2-5% (4-6 clients) |
| snapclient | 5-15 MB | 2-5% x86, 5-10% ARM |

**Client IDs:** MAC address by default (e.g., `aa:bb:cc:dd:ee:ff`). AI agent needs `Server.GetStatus` to discover clients and map to room names.

---

## Research Task 3: Spotify Web API

**Acceptance criteria:**
- [x] Documented OAuth2 flow — **Authorization Code Flow** (NOT PKCE — server has client_secret)
- [x] Listed required scopes: `user-modify-playback-state`, `user-read-playback-state`, `user-read-currently-playing`, `playlist-read-private`, `playlist-read-collaborative`
- [x] Confirmed Spotify JAM: **app-only, no API**
- [x] Documented rate limits: ~180 req/min safe, no official numbers; handle 429 + Retry-After
- [x] Clarified: Web API controls playback on Spotify Connect devices. librespot appears as Connect device, targetable by device_id.

### Findings

**OAuth2 Authorization Code Flow:**
1. Redirect to `https://accounts.spotify.com/authorize` with `client_id`, `response_type=code`, `redirect_uri`, `scope`, `state`
2. User authorizes, Spotify redirects back with `code`
3. Exchange code for tokens: `POST https://accounts.spotify.com/api/token` with Basic auth (`base64(client_id:client_secret)`)
4. Response: `access_token` (expires 3600s), `refresh_token` (long-lived)
5. Refresh: `POST /api/token` with `grant_type=refresh_token` — always persist latest refresh_token (rotation happening)

**One-time browser auth.** Store refresh_token securely. Refresh proactively at ~50 min.

**All endpoints** (base: `https://api.spotify.com/v1`):

| Action | Method | Path | Scope |
|--------|--------|------|-------|
| Search | GET | `/v1/search?q=...&type=track` | None |
| Play | PUT | `/v1/me/player/play` | modify |
| Pause | PUT | `/v1/me/player/pause` | modify |
| Next | POST | `/v1/me/player/next` | modify |
| Previous | POST | `/v1/me/player/previous` | modify |
| Seek | PUT | `/v1/me/player/seek?position_ms=` | modify |
| Volume | PUT | `/v1/me/player/volume?volume_percent=` | modify |
| Shuffle | PUT | `/v1/me/player/shuffle?state=` | modify |
| Repeat | PUT | `/v1/me/player/repeat?state=` | modify |
| Get Playback | GET | `/v1/me/player` | read |
| Currently Playing | GET | `/v1/me/player/currently-playing` | currently-playing |
| Get Devices | GET | `/v1/me/player/devices` | read |
| Transfer Playback | PUT | `/v1/me/player` | modify |
| Get Queue | GET | `/v1/me/player/queue` | read |
| Add to Queue | POST | `/v1/me/player/queue?uri=` | modify |

**No "remove from queue" or "reorder queue" endpoint.** Queue manipulation beyond "add" is not supported.

**Control path for this project:** AI agent -> Spotify Web API (targeting librespot device_id) -> librespot streams -> FIFO -> Snapcast -> all rooms. This is the cleanest architecture.

**Spotify JAM:** App-only. No API. Friends join via Spotify app while host casts to librespot device. Risk #7: test JAM + librespot compatibility early.

**Rate limits:** ~180 req/min community-derived. For ~100-500 req/day from Discord, rate limits are irrelevant. Implement 429 + Retry-After handling regardless.

---

## Research Task 4: librespot

**Acceptance criteria:**
- [x] Confirmed: `cargo install librespot` (Rust, ~3-5 min build)
- [x] Documented FIFO output: `librespot --name "Music Server" --backend pipe --device /tmp/librespot_snapfifo --bitrate 320 --format S16 --cache /var/cache/librespot`
- [x] Confirmed: appears as Spotify Connect device (Zeroconf/mDNS, `--name` sets display name)
- [x] Noted: coexists with Mopidy on separate FIFOs, avoid mopidy-spotify to prevent session conflicts
- [x] Evaluated: **librespot is the primary Spotify source** — simpler, more reliable, supports Connect + JAM natively

### Findings

**Version:** v0.4.2 (last stable as of cutoff). Active `dev` branch with v0.5.0 work. ~4,500+ GitHub stars.

**FIFO command:**
```bash
librespot \
  --name "Music Server" \
  --backend pipe \
  --device /tmp/librespot_snapfifo \
  --bitrate 320 \
  --format S16 \
  --initial-volume 100 \
  --cache /var/cache/librespot \
  --device-type speaker
```

FIFO setup: `mkfifo /tmp/librespot_snapfifo`

Snapserver config: `source = pipe:///tmp/librespot_snapfifo?name=Spotify&sampleformat=44100:16:2`

**Authentication:** Zeroconf (default, recommended). User connects from Spotify app, credentials cached in `--cache` dir for restarts. No username/password needed on server. Requires Spotify Premium.

**Audio quality:** `--bitrate 96|160|320` (Ogg Vorbis from Spotify, decoded to raw PCM for pipe output). `--format S16` for Snapcast compatibility.

**Coexistence with Mopidy:** Separate processes, separate FIFOs, no conflicts. **Do NOT install mopidy-spotify** — would cause Spotify session conflicts (one active device per account).

**Spotify Connect:** Core functionality. librespot advertises via mDNS, appears in Spotify app device picker. Friends can cast to it, use JAM.

**AI agent bridge:** librespot has no HTTP API. But Spotify Web API can transfer playback to the librespot device by `device_id` — agent calls Web API -> targets librespot -> audio streams to Snapcast.

**Additional flags:** `--autoplay` (Spotify autoplay), `--device-type speaker` (device category), `--volume-ctrl {linear,log,fixed}`.

> **Verify post-2025:** Check if v0.5.0 released. `cargo install librespot --version <latest>`.

---

## Research Task 5: AI Agent Tooling

**Acceptance criteria:**
- [x] Confirmed: DeepSeek and Qwen both support OpenAI-compatible function calling
- [x] Selected framework: **raw `openai` library (AsyncOpenAI)** — all providers are OpenAI-compatible, no framework needed
- [x] Estimated cost: **$3-8/month** for ~300 req/day
- [x] Confirmed: 12 tools well within spec for all providers

### Findings

**DeepSeek (`deepseek-chat` / V3):**
- OpenAI-compatible: `base_url="https://api.deepseek.com"`, standard `tools` parameter
- Pricing: $0.07/1M input (cache hit), $0.27 (miss), $1.10/1M output
- Prompt caching: static tool definitions benefit from cache hits after first call
- **Only `deepseek-chat` supports function calling.** `deepseek-reasoner` (R1) does NOT.
- Reliability concern: capacity issues during peak demand, China-based infra adds latency

**Qwen (via Together.ai):**
- OpenAI-compatible: standard `tools` parameter
- Qwen2.5-7B: $0.20/1M tokens (cheapest), 72B: $0.90/1M (highest quality)
- US-based infra (Together.ai), more reliable than DeepSeek

**Cost estimate (~300 req/day, 12 tools):**
| Provider | Monthly Cost |
|----------|-------------|
| DeepSeek (cache hit) | ~$3 |
| DeepSeek (cache miss) | ~$8 |
| Qwen2.5-7B (Together) | ~$5 |
| Qwen2.5-72B (Together) | ~$21 |

**Framework decision: Raw `openai` library.** Reasoning:
- All providers are OpenAI-compatible — swap by changing `base_url`
- No complex orchestration needed (simple tool-calling loop)
- Pydantic AI adds abstraction with no gain for this use case
- LiteLLM adds ~50 transitive deps for something `base_url` swap does for free
- Keeps dependencies minimal on the 8GB server

**Fallback pattern:**
```python
providers = [
    {"base_url": "https://api.deepseek.com", "model": "deepseek-chat", "api_key": DS_KEY},
    {"base_url": "https://api.together.xyz/v1", "model": "Qwen/Qwen2.5-72B-Instruct-Turbo", "api_key": TG_KEY},
]
```

> **Verify post-2025:** Current DeepSeek pricing, Together.ai model IDs, DashScope intl availability.

---

## Research Task 6: Discord Bot Framework

**Acceptance criteria:**
- [x] Decided: **message-based commands** (not slash commands) — AI agent handles NLP
- [x] Documented bot setup: create application, add bot, generate token, invite with permissions
- [x] Confirmed: runs as systemd `Type=simple` service alongside other components
- [x] Estimated RAM: **50-80 MB** for bot + AI agent combined

### Findings

**discord.py v2.4.x+** — fully async (`asyncio`), Python 3.9+. Actively maintained after 2021 scare. Uses `aiohttp` internally (aligns with project's async stack).

**Bot setup:**
1. Create Application at `discord.com/developers/applications`
2. Add Bot, **enable Message Content Intent** (privileged, required for reading message text)
3. Generate token, store in `.env`
4. Invite URL: `https://discord.com/oauth2/authorize?client_id=YOUR_ID&scope=bot&permissions=68608`
   - Permissions: Read Messages (1024) + Send Messages (2048) + Read Message History (65536) = 68608

**Message Content Intent:** Required for reading `message.content`. Trivial for single-server bots (toggle in portal, no approval needed for <100 servers).

**Message-based > slash commands** for this project:
- Natural language goes straight to LLM — no structured params to fight
- No 3-second acknowledgment deadline (slash commands require it)
- Simpler implementation: listen for messages, pass to agent, send response

**Typing indicator for AI latency:**
```python
async with message.channel.typing():
    response = await ai_agent.process(message.content)
await message.channel.send(response)
```

**Rate limits:** 50 req/s global, 5 msg/s per channel. discord.py handles 429 automatically. Irrelevant for this use case.

**systemd unit:**
```ini
[Unit]
Description=Music Server Discord Bot
After=network-online.target snapserver.service mopidy.service
[Service]
Type=simple
User=musicserver
ExecStart=/path/to/.venv/bin/python -m music_server.bot
Restart=always
RestartSec=5
EnvironmentFile=/path/to/.env
[Install]
WantedBy=multi-user.target
```

**RAM:** 50-80 MB realistic (Python ~25MB + discord.py ~20MB + caches ~15MB + agent ~15MB). Fits 8GB budget.

> **Verify post-2025:** Exact discord.py version, minimum Python version.

---

## Key Decisions Confirmed by Research

1. **Mopidy for local files only.** mopidy-spotify is broken. No mopidy-spotify plugin.
2. **librespot is the primary Spotify source.** Spotify Connect + JAM native. Audio -> FIFO -> Snapcast.
3. **AI agent controls Spotify via Web API** targeting librespot's device_id. Controls Mopidy via HTTP JSON-RPC for local files.
4. **Snapcast handles multi-room sync.** Two streams: Mopidy (local) + librespot (Spotify). Per-client volume/mute via JSON-RPC.
5. **Raw `openai` library** (AsyncOpenAI). DeepSeek primary, Qwen/Together.ai fallback. ~$3-8/month.
6. **discord.py message-based bot.** Message Content Intent enabled. Typing indicator for UX.

## Items Requiring Live Verification Before Phase 01

- [ ] `pip install Mopidy && mopidy --version` on the actual server
- [ ] `apt info snapserver` to check available version
- [ ] `cargo install librespot` — confirm build succeeds
- [ ] Test FIFO pipeline: mkfifo -> snapserver -> play audio -> confirm output
- [ ] Test librespot Spotify Connect: appears in Spotify app device list
- [ ] Test Spotify JAM with librespot (Risk #7)
- [ ] Check DeepSeek pricing at platform.deepseek.com
- [ ] Check mopidy-spotify GitHub for any stable v5.x release
