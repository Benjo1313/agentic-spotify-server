# Phase 5: Discord Bot Integration

> **Status:** Not started
> **Dependencies:** 04-ai-agent.md (AI agent must be working via CLI)
> **Parallelizable with:** Nothing — wraps the AI agent

## Overview

Wrap the AI agent in a Discord bot so users can control music and rooms by typing natural language in a Discord channel.

---

## Tasks

1. Install discord.py: `pip install discord.py`
2. Build the Discord bot (`bot/discord_bot.py`):
   - Connect using bot token from `.env`
   - Listen for messages in a designated channel (or all channels the bot is in)
   - Ignore messages from other bots (including itself)
   - Pass message content to the AI agent
   - Send agent's text response back to the channel
   - Add typing indicator while the agent is thinking
3. Add rate limiting: max 1 request per user per 2 seconds
4. Add a `!help` escape hatch (non-AI) that lists example commands:
   ```
   Examples:
   - "Play Blue Train by Coltrane"
   - "Skip this song"
   - "What's playing?"
   - "Mute the kitchen"
   - "Set living room volume to 50"
   - "List all rooms"
   ```
5. Invite the bot to target Discord server:
   - Permissions needed: Read Messages, Send Messages, Read Message History
   - No voice channel permissions needed
6. Test with real users in Discord

---

## Done Criteria

- [ ] Bot connects to Discord and responds to messages
- [ ] Natural language commands work end-to-end (Discord -> Agent -> Spotify/Snapcast -> audio)
- [ ] Rate limiting prevents spam
- [ ] `!help` shows examples
- [ ] Bot ignores its own messages and other bots
- [ ] Typing indicator shows while agent is processing

---

## Technical Notes

- **Framework:** discord.py v2.x (async, well-maintained)
- **Message handling:** Message-based, NOT slash commands — the AI agent handles all natural language parsing
- **Error handling:** If the agent fails, send a user-friendly error message to Discord (not a stack trace)
- **RAM estimate:** ~50-80MB for the bot process (includes discord.py + aiohttp)
