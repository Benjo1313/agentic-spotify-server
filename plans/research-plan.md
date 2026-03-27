# Multi-Room Music Server: Plan Index

## Architecture
- [architecture.md](architecture.md) — Component diagram, data flows, risks, tech decisions

## Phases (in dependency order)

| File | Phase | Depends On | Can Parallelize With |
|------|-------|------------|---------------------|
| [00-research.md](00-research.md) | Research (all 6 tasks) | Nothing | All 6 tasks run in parallel |
| [01-server-infra.md](01-server-infra.md) | Server setup + Snapcast deployment | 00-research | 02 (partially) |
| [02-music-sources.md](02-music-sources.md) | Mopidy + librespot | 01-server-infra | Config can be written during 01 |
| [03-api-clients.md](03-api-clients.md) | Spotify + Snapcast Python clients | 02-music-sources | Spotify client and Snapcast client in parallel |
| [04-ai-agent.md](04-ai-agent.md) | AI agent with tool-use + CLI | 03-api-clients | — |
| [05-discord-bot.md](05-discord-bot.md) | Discord bot wrapping the agent | 04-ai-agent | — |
| [06-polish.md](06-polish.md) | systemd, health checks, node scripts | All prior phases | Node scripts in parallel with systemd work |

## Parallelism Map

```
00-research (all 6 tasks in parallel)
    |
    v
01-server-infra ----+
    |               |
    v               v (config only)
02-music-sources    |
    |               |
    v               |
03-api-clients -----+
  |           |
  v           v
  Spotify    Snapcast  (parallel agents)
  client     client
    |           |
    +-----+-----+
          |
          v
    04-ai-agent
          |
          v
    05-discord-bot
          |
          v
    06-polish
```
