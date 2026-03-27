# Phase 1: Server Infrastructure + Snapcast Deployment

> **Status:** Not started
> **Dependencies:** 00-research.md (Snapcast research tasks completed)
> **Parallelizable with:** 02-music-sources.md (partially — Mopidy config can be written, but end-to-end test requires Snapcast running)

## Overview

Set up the HP ProDesk server, install all system dependencies, deploy Snapcast server + clients on all nodes, and verify synchronized audio playback across the network.

---

## Part A: Server Setup and Base Infrastructure

**Delivers:** A clean server ready to host all services, with development tools installed.

**Tasks:**
1. Update Linux Mint: `sudo apt update && sudo apt upgrade`
2. Install system dependencies: `sudo apt install python3 python3-pip python3-venv git curl build-essential`
3. Install Rust toolchain (for librespot): `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
4. Create project directory structure:
   ```
   /home/benjo/Projects/music-server/
   ├── bot/                  # Discord bot + AI agent
   ├── config/               # Configuration files
   │   ├── snapserver.conf
   │   ├── mopidy.conf
   │   └── .env              # Secrets (Spotify, Discord, AI API keys)
   ├── scripts/              # Setup and maintenance scripts
   ├── systemd/              # Service unit files
   ├── plans/                # Plan files
   └── tests/                # Test files
   ```
5. Create `.env` file with placeholders for all required secrets:
   ```
   SPOTIFY_CLIENT_ID=
   SPOTIFY_CLIENT_SECRET=
   SPOTIFY_REFRESH_TOKEN=
   DISCORD_BOT_TOKEN=
   DEEPSEEK_API_KEY=
   ```
6. Set up a Python virtual environment: `python3 -m venv .venv`
7. Create a Spotify Developer Application at https://developer.spotify.com/dashboard
8. Create a Discord Application and Bot at https://discord.com/developers/applications

**Done criteria:** Server is updated, all system dependencies installed, project directory exists, Spotify and Discord developer accounts created with tokens in `.env`.

---

## Part B: Snapcast Server + Client Deployment

**Delivers:** Synchronized audio playback across all nodes. Audio from a test source plays on all connected nodes in sync.

**Tasks:**
1. Install Snapcast server: `sudo apt install snapserver`
2. Configure `/etc/snapserver.conf`:
   ```ini
   [stream]
   source = pipe:///tmp/mopidy_snapfifo?name=Mopidy&sampleformat=48000:16:2
   source = pipe:///tmp/librespot_snapfifo?name=Spotify&sampleformat=44100:16:2

   [http]
   enabled = true
   port = 1780
   ```
3. Create FIFO pipes:
   ```bash
   mkfifo /tmp/mopidy_snapfifo
   mkfifo /tmp/librespot_snapfifo
   ```
4. Start Snapcast server: `sudo systemctl enable --now snapserver`
5. Install Snapcast client on server: `sudo apt install snapclient`
6. Install Snapcast clients on other nodes:
   - **Windows**: Download from https://github.com/badaix/snapcast/releases
   - **macOS**: `brew install snapcast`
   - **Mini PCs (Linux)**: `sudo apt install snapclient`
7. Configure each client with a friendly name: `snapclient --hostID living_room --host <server_ip>`
8. Test with synthetic audio:
   ```bash
   ffmpeg -f lavfi -i "sine=frequency=440:duration=5" -f s16le -ar 48000 -ac 2 /tmp/mopidy_snapfifo
   ```
9. Verify all clients receive and play the test tone in sync
10. Set up auto-start for clients on each node OS

**Done criteria:** Test tone plays simultaneously on all connected nodes. Each node appears in Snapcast status with its friendly name. Volume can be adjusted per-node via the JSON-RPC API.

---

## Network Requirements

| Protocol | Port | Direction | Purpose |
|----------|------|-----------|---------|
| TCP | 1704 | Server -> Nodes | Snapcast audio stream |
| TCP | 1705 | Server -> Nodes | Snapcast control |
| TCP | 1780 | Localhost only | Snapcast JSON-RPC API |

Firewall: Open port 1704 on LAN for Snapcast clients.

## Per-Node Configuration

Each node needs:
1. **Snapcast client** installed and configured to connect to server IP
2. **Audio output** configured at OS level (USB, 3.5mm, HDMI, or Bluetooth)
3. **Friendly name** set in Snapcast client config (e.g., `--hostID kitchen`)
4. **Auto-start** on boot (systemd on Linux, Task Scheduler on Windows, launchd on macOS)
