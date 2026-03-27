# Phase 6: Polish and Reliability

> **Status:** Not started
> **Dependencies:** All prior phases (00-05)
> **Parallelizable:** Node setup scripts can be written in parallel with systemd/health work

## Overview

Make the system production-ready: auto-start on boot, recover from failures, easy node onboarding.

---

## Tasks

### systemd Services

1. Create service files for all server-side services:
   - `snapserver.service` (likely exists from apt install)
   - `snapclient.service` (server's own client)
   - `mopidy.service`
   - `librespot.service`
   - `music-bot.service` (Discord bot + AI agent)
2. Configure service dependencies:
   ```ini
   # music-bot.service
   [Unit]
   After=snapserver.service mopidy.service librespot.service
   Requires=snapserver.service
   ```

### Health Checks and Error Handling

3. Bot pings Mopidy and Snapcast on startup, logs warnings if unavailable
4. Periodic health check (every 5 minutes) with auto-reconnect
5. Spotify token refresh failure: notify via Discord, attempt re-auth
6. Snapcast client disconnect: agent reports "kitchen is offline" instead of crashing
7. Network outage: graceful degradation (local files still work)

### Logging

8. Structured logging to journald
9. Log all agent tool calls and results (for debugging)
10. Log errors with enough context to diagnose remotely

### Node Management

11. Node auto-discovery from Snapcast `Server.GetStatus` on bot startup
12. Dynamic name map (no hardcoded client IDs)
13. Support renaming nodes via Discord: "rename node abc123 to kitchen"

### Setup Scripts for New Nodes

14. `scripts/setup-linux-node.sh`
15. `scripts/setup-windows-node.ps1`
16. `scripts/setup-macos-node.sh`

---

## Done Criteria

- [ ] All services start automatically on boot
- [ ] System recovers from temporary failures (network blips, Spotify token expiry)
- [ ] Logs are accessible via `journalctl`
- [ ] New nodes can be added with a setup script
- [ ] Node auto-discovery works (no manual ID mapping needed)
- [ ] Non-technical friends can use the Discord bot without guidance
