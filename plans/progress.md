# Music Server — Progress Tracker

> Updated after each session. Shows what's done, what's in progress, and what's next.

---

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| 00 — Research | ✅ Complete | All 6 tasks done. Key finding: mopidy-spotify broken, use librespot. |
| 01 — Server Infrastructure | ✅ Complete* | *snapclient on server deferred (no audio output connected yet) |
| 02 — Music Sources | ✅ Complete | Mopidy + FIFO pipeline to Snapcast; mopidy-local/mpd via venv PYTHONPATH drop-in |
| 03 — API Clients | ✅ Complete | SpotifyClient (aiohttp), SnapcastClient (requests+to_thread workaround) |
| 04 — AI Agent | ✅ Complete | DeepSeek via OpenAI SDK; 12 tools; bounded conversation history |
| 05 — Discord Bot | ✅ Complete | #spotify-chat channel filter + @mention; rate limiting; typing indicator |
| 06 — Polish | 🔄 In Progress | systemd ✅, tool logging ✅, health check ✅, linux node script ✅ |

---

## Phase 01 Details

### What's Done
- System deps: Python 3.12.3, pip3, venv, Rust 1.94.1, git, curl, build-essential
- Project directories: `bot/`, `config/`, `scripts/`, `systemd/`, `tests/`
- `config/.env` created — Spotify and Discord credentials filled in
- Spotify Developer App created (redirect URI: `http://127.0.0.1:8888/callback`)
- Discord Bot created with Message Content Intent enabled
- Snapcast v0.31.0 running — config at `/etc/snapserver.conf`
  - Mopidy FIFO source: `pipe:///tmp/mopidy_snapfifo?name=Mopidy&mode=create&sampleformat=48000:16:2`
  - Spotify source: `librespot:///usr/local/bin/librespot?name=Spotify...` (native Snapcast integration)
- librespot v0.6.0-dev spawned by snapserver, Spotify Connect published via Avahi
- Passwordless sudo configured at `/etc/sudoers.d/claude-music` (systemctl, cp, mkfifo)

### Deferred Items
- **snapclient ALSA device on server** — `/etc/default/snapclient` has a placeholder. Once audio output is connected: run `aplay -l`, find card/device, add `--player alsa:device=hw:X,X` to `SNAPCLIENT_OPTS`
- **snapclient on nodes** (Windows, macOS, Mini PCs) — deferred to Phase 06
- **ffmpeg sine tone test** — deferred until audio output connected

---

## Open Items / Blockers

| Item | Needed For | Notes |
|------|-----------|-------|
| `SPOTIFY_REFRESH_TOKEN` | Phase 03 | OAuth flow not yet run |
| `DEEPSEEK_API_KEY` | Phase 04 | Sign up at https://platform.deepseek.com |
| Audio output on server | Phase 01 deferred | Plug in, run `aplay -l`, update `/etc/default/snapclient` |

---

## Key Decisions Made

- **librespot via native Snapcast integration** — Snapcast spawns librespot directly (`librespot://` source), not via FIFO pipe. Cleaner lifecycle management.
- **Mopidy uses FIFO pipe** — GStreamer output → `/tmp/mopidy_snapfifo` → Snapcast `pipe://` source
- **No mopidy-spotify** — broken (libspotify deprecated). librespot handles all Spotify playback.
- **Spotify Web API** targets librespot by device_id for AI agent control
- **AI provider**: DeepSeek primary, Qwen/Together.ai fallback (all OpenAI-compatible)
- **Discord bot**: message-based (not slash commands), AI handles NLP
