# Phase 3: API Clients (Spotify + Snapcast)

> **Status:** Not started
> **Dependencies:** 02-music-sources.md (Mopidy and Snapcast must be running)
> **Parallelizable:** Spotify client and Snapcast client can be built by separate agents simultaneously

## Overview

Build the Python API clients that the AI agent will use to control Spotify playback and Snapcast room management. These are the "hands" of the AI — everything the agent does goes through these clients.

---

## Part A: Spotify API Client

> Can be built in parallel with Part B

**Delivers:** `bot/spotify_client.py` — async Spotify Web API client with token management.

**Tasks:**
1. Implement OAuth2 Authorization Code flow:
   - Scopes: `user-modify-playback-state`, `user-read-playback-state`, `user-read-currently-playing`, `user-read-recently-played`
   - Build a one-time auth script that opens a browser, captures the callback, stores a refresh token
   - Store refresh token in `.env`
2. Build Spotify API client module (`bot/spotify_client.py`):
   - Token refresh logic (access tokens expire every 60 minutes)
   - Search tracks: `GET /v1/search?type=track&q={query}`
   - Get current playback: `GET /v1/me/player`
   - Play track: `PUT /v1/me/player/play`
   - Pause: `PUT /v1/me/player/pause`
   - Skip: `POST /v1/me/player/next`
   - Add to queue: `POST /v1/me/player/queue?uri=spotify:track:xxx`
   - Get queue: `GET /v1/me/player/queue`
3. Write integration tests against the live Spotify API

**Done criteria:**
- [ ] OAuth2 flow works, refresh token stored
- [ ] All 7 Spotify operations work programmatically
- [ ] Token auto-refresh works (simulate expiry)
- [ ] Tests pass

---

## Part B: Snapcast API Client

> Can be built in parallel with Part A

**Delivers:** `bot/snapcast_client.py` — async Snapcast JSON-RPC client with room name resolution.

**Tasks:**
1. Build Snapcast API client module (`bot/snapcast_client.py`):
   - Connect to `http://localhost:1780/jsonrpc`
   - `Server.GetStatus` — list all clients and groups
   - `Client.SetVolume` — set volume and mute per client
   - `Group.SetStream` — switch which stream a group listens to
2. Build a name resolver for Snapcast nodes:
   - Map friendly names ("kitchen", "living room") to Snapcast client IDs
   - Support fuzzy matching (e.g., "livingroom" matches "living_room")
   - Config file or auto-discovery from `Server.GetStatus`
3. Write integration tests against the running Snapcast server

**Done criteria:**
- [ ] All Snapcast operations work programmatically
- [ ] Name resolver maps friendly names to client IDs
- [ ] Fuzzy matching works for common variations
- [ ] Tests pass

---

## Technical Notes

- **Language:** Python (async with aiohttp)
- **HTTP client:** aiohttp (matches discord.py's async model)
- **Validation:** pydantic for settings and response parsing
- **Spotify client:** Raw aiohttp, NOT spotipy (spotipy is synchronous)

## Key API References

| API | Base URL | Docs |
|-----|----------|------|
| Spotify Web API | `https://api.spotify.com/v1` | https://developer.spotify.com/documentation/web-api/reference |
| Snapcast JSON-RPC | `http://localhost:1780/jsonrpc` | https://github.com/badaix/snapcast/blob/master/doc/json_rpc_api/control.md |
