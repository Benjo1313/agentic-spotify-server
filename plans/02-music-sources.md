# Phase 2: Music Sources (Mopidy + librespot)

> **Status:** Not started
> **Dependencies:** 01-server-infra.md (Snapcast must be running)
> **Parallelizable with:** Config can be written while Phase 1 is in progress; end-to-end testing requires Snapcast

## Overview

Set up Mopidy for local file playback and librespot for Spotify Connect, both piping audio into Snapcast for synchronized multi-room output.

---

## Tasks

### Mopidy Setup

1. Install Mopidy and extensions:
   ```bash
   sudo apt install mopidy
   pip install mopidy-local mopidy-mpd
   ```
2. Attempt to install mopidy-spotify:
   ```bash
   pip install mopidy-spotify
   ```
   - If it works: configure with Spotify credentials
   - If broken: skip, rely on librespot (see below)
3. Configure Mopidy:
   ```ini
   [audio]
   output = audioresample ! audioconvert ! audio/x-raw,rate=48000,channels=2,format=S16LE ! filesink location=/tmp/mopidy_snapfifo

   [http]
   enabled = true
   hostname = 127.0.0.1
   port = 6680

   [local]
   media_dir = /home/benjo/Music
   ```
4. Add local music files to `/home/benjo/Music/` and run `mopidy local scan`
5. Test local file playback via Mopidy HTTP API:
   ```bash
   curl -X POST http://localhost:6680/mopidy/rpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"core.library.browse","params":{"uri":"local:directory"}}'
   ```

### librespot Setup

6. Install librespot:
   ```bash
   cargo install librespot
   ```
7. Configure librespot to output to Snapcast FIFO:
   ```bash
   librespot --name "Music Server" \
             --backend pipe \
             --device /tmp/librespot_snapfifo \
             --bitrate 320 \
             --enable-volume-normalisation \
             --initial-volume 100 \
             --device-type speaker
   ```
8. Test Spotify playback via librespot (cast from Spotify app to "Music Server")

### End-to-End Verification

9. Verify local files play on all nodes via Mopidy -> Snapcast
10. Verify Spotify plays on all nodes via librespot -> Snapcast
11. Verify both streams are selectable in Snapcast (Mopidy stream vs Spotify stream)

---

## Done Criteria

- [ ] Local files play on all nodes via Mopidy
- [ ] Spotify plays on all nodes via librespot
- [ ] Both streams are selectable in Snapcast
- [ ] Mopidy HTTP API responds on :6680
- [ ] librespot appears as "Music Server" in Spotify Connect device list

---

## Architecture Decision Point

After this phase, decide whether to keep both Mopidy and librespot, or simplify:

- **Option A (Recommended):** Mopidy for local files + search/queue API, librespot for Spotify Connect/JAM. Two Snapcast streams. AI agent controls Mopidy for local, Spotify Web API for Spotify.
- **Option B:** Mopidy with mopidy-spotify for everything (if the plugin works reliably). Single stream. AI agent controls only Mopidy API.

Document the decision before proceeding to Phase 3.
