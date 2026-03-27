# Architecture Reference

> Shared context for all plan files. This document describes how components fit together, data flows, risks, and technical decisions.

## Component Diagram

```
+------------------------------------------------------------------+
|                    HP ProDesk Server (Linux Mint)                  |
|                                                                    |
|  +-------------+     FIFO      +---------------+                  |
|  |   Mopidy    |---- pipe ---->|  Snapcast     |                  |
|  | (local files)| /tmp/mopidy  |  Server       |---- TCP:1704 -->|-> to all nodes
|  +-------------+  _snapfifo   |  (snapserver)  |                  |
|                                |               |                  |
|  +-------------+     FIFO      |               |                  |
|  |  librespot  |---- pipe ---->| (multi-stream) |                  |
|  | (Spotify    | /tmp/libre    |               |                  |
|  |  Connect)   |  spot_fifo   +---------------+                  |
|  +-------------+                      |                            |
|        ^                              |                            |
|        |                     +--------v--------+                  |
|  Spotify Connect             | Snapcast Client |                  |
|  (friends cast here,        | (local node -    |                  |
|   JAM sessions)             |  server is also  |                  |
|                              |  an audio output) |                  |
|                              +-----------------+                  |
|                                                                    |
|  +------------------+    HTTP/JSON    +------------------+        |
|  |  Discord Bot     |<-------------->|  AI Agent        |        |
|  |  (discord.py)    |                |  (tool-use LLM)  |        |
|  +------------------+                +------------------+        |
|         ^                              |           |              |
|         |                    Mopidy    |  Snapcast |              |
|    Discord API               HTTP API  |  JSON-RPC |              |
|         |                    :6680     |  :1780    |              |
|         v                              v           v              |
|    Discord Server            Mopidy         Snapcast              |
|    (cloud)                   (local)        (local)               |
+------------------------------------------------------------------+

         Network (LAN)
              |
    +---------+---------+---------+
    |         |         |         |
+---v---+ +---v---+ +---v---+ +---v---+
|Windows| |MacBook| |Mini   | |Mini   |
|Desktop| |       | |PC #1  | |PC #2  |
|       | |       | |       | |       |
|Snap   | |Snap   | |Snap   | |Snap   |
|Client | |Client | |Client | |Client |
+-------+ +-------+ +-------+ +-------+
 USB/HDMI  3.5mm/BT   USB      USB/BT
```

## Data Flows

### "Play Blue Train by Coltrane"

```
User (Discord) --> Discord Bot --> AI Agent (LLM)
                                        |
                                   Tool call: search_tracks("Blue Train Coltrane")
                                        |
                                   Mopidy HTTP API: core.library.search
                                        |
                                   Returns track URIs
                                        |
                                   Tool call: play_track("spotify:track:xxx")
                                        |
                                   Mopidy HTTP API: core.tracklist.add + core.playback.play
                                        |
                                   Mopidy --> GStreamer --> FIFO --> Snapcast --> All nodes
```

### "Mute the Kitchen"

```
User (Discord) --> Discord Bot --> AI Agent (LLM)
                                        |
                                   Tool call: mute_room("kitchen")
                                        |
                                   Resolve "kitchen" to Snapcast client ID
                                        |
                                   Snapcast JSON-RPC: Client.SetVolume (muted: true)
                                        |
                                   Kitchen node goes silent (others continue)
```

### Friend Adds Song via Spotify JAM

```
Friend (Spotify app) --> Joins JAM on librespot device
                              |
                         Spotify manages queue in-app
                              |
                         librespot receives stream --> FIFO --> Snapcast --> All nodes
```

> **Note:** Spotify JAM is app-only. No API. Friends interact via Spotify app.

## Service Inventory

| Service | Runs On | Port | Purpose |
|---------|---------|------|---------|
| `snapserver` | Server | 1704, 1705, 1780 | Audio distribution + control API |
| `snapclient` | Server + all nodes | N/A | Audio playback |
| `mopidy` | Server | 6680 | Music server (local + Spotify) |
| `librespot` | Server | N/A | Spotify Connect receiver |
| Discord bot + AI agent | Server | N/A | User interface + NLP |

## Network Requirements

| Protocol | Port | Direction | Purpose |
|----------|------|-----------|---------|
| TCP | 1704 | Server -> Nodes | Snapcast audio stream |
| TCP | 1705 | Server -> Nodes | Snapcast control |
| TCP | 1780 | Localhost only | Snapcast JSON-RPC API |
| TCP | 6680 | Localhost only | Mopidy HTTP API |
| TCP | 443 | Server -> Internet | Spotify API, Discord API, AI API |
| TCP | 4070 | Server -> Internet | Spotify (librespot) |

## Language & Framework Decisions

**Language: Python**
- Mopidy is Python (native ecosystem)
- discord.py v2.x (async)
- openai library for AI agent (raw function calling, no framework)
- aiohttp for async HTTP (Spotify API, Snapcast JSON-RPC)
- pydantic for config/validation

## RAM Budget

| Component | Estimated RAM |
|-----------|---------------|
| Linux Mint (idle) | ~1.2 GB |
| Snapcast server | ~15-20 MB |
| Snapcast client (local) | ~10 MB |
| Mopidy | ~60-80 MB |
| librespot | ~20-30 MB |
| Discord bot + AI agent | ~60-100 MB |
| **Total** | **~1.4-1.5 GB** |

Leaves ~6.5 GB headroom on the 8GB machine.

## Risks and Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | mopidy-spotify unmaintained/broken | High | Medium | librespot is primary Spotify source. Mopidy handles local files. |
| 2 | Snapcast client difficult on macOS | Medium | Medium | Homebrew formula exists. Fallback: build from source or AirPlay bridge. |
| 3 | Bluetooth audio latency on nodes | Medium | Low | Snapcast configurable latency offset per client. |
| 4 | Spotify API rate limiting | Low | Low | Cache search results. Rate limit Discord commands. |
| 5 | 8GB RAM insufficient | Low | High | Estimated ~1.5GB total. Monitor with `htop`. |
| 6 | DeepSeek/Qwen API unreliable | Medium | Medium | OpenAI-compatible. Swap providers by changing `base_url`. |
| 7 | Spotify JAM not working with librespot | Medium | Low | Fallback: collaborative playlists via API. |
| 8 | FIFO pipe buffer issues | Medium | Medium | Use Snapcast `buffer_ms` setting. |
| 9 | Cross-platform Snapcast auto-start | Low | Low | systemd / launchd / Task Scheduler scripts per OS. |
| 10 | AI agent hallucinating tool calls | Medium | Low | Validate params before execution. Return clear errors. |

## Key Repository Links

| Component | Repository |
|-----------|-----------|
| Mopidy | https://github.com/mopidy/mopidy |
| mopidy-spotify | https://github.com/mopidy/mopidy-spotify |
| Snapcast | https://github.com/badaix/snapcast |
| librespot | https://github.com/librespot-org/librespot |
| discord.py | https://github.com/Rapptz/discord.py |
| Spotify Web API | https://developer.spotify.com/documentation/web-api |
| DeepSeek API | https://platform.deepseek.com/docs |
| OpenAI Python SDK | https://github.com/openai/openai-python |
