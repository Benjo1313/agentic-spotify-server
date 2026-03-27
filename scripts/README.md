# Adding a New Audio Node

A node is any machine that plays audio from the music server. Once connected, it appears in Discord and you can control its volume independently.

**Prerequisites:** The music server must be running and reachable on your LAN.

---

## Linux

```bash
curl -fsSL https://raw.githubusercontent.com/<you>/music-server/main/scripts/setup-linux-node.sh \
  | bash -s -- --server <server-ip> --name "kitchen"
```

Or if you have the repo cloned:

```bash
bash scripts/setup-linux-node.sh --server 192.168.1.10 --name "kitchen"
```

The script will:
1. Install `snapclient` via apt/dnf/pacman
2. Auto-detect your ALSA audio device
3. Write `/etc/default/snapclient` and enable the systemd service

If the ALSA device isn't detected correctly, find it manually:
```bash
aplay -l
# Look for a line like: card 1: Device [USB Audio], device 0
```
Then edit `/etc/default/snapclient` and set `--player alsa:device=hw:1,0`.

---

## macOS

Requires [Homebrew](https://brew.sh).

```bash
curl -fsSL https://raw.githubusercontent.com/<you>/music-server/main/scripts/setup-macos-node.sh \
  | bash -s -- --server <server-ip> --name "bedroom"
```

Or with the repo cloned:

```bash
bash scripts/setup-macos-node.sh --server 192.168.1.10 --name "bedroom"
```

The script will:
1. Install `snapcast` via Homebrew
2. Create a launchd service at `~/Library/LaunchAgents/com.snapcast.snapclient.plist`
3. Start it immediately and on every login

Logs: `tail -f /tmp/snapclient.log`

To stop/remove:
```bash
launchctl unload ~/Library/LaunchAgents/com.snapcast.snapclient.plist
```

---

## Windows

Run PowerShell **as Administrator**, then:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/<you>/music-server/main/scripts/setup-windows-node.ps1))) -Server <server-ip> -Name "office"
```

Or with the repo cloned:

```powershell
.\scripts\setup-windows-node.ps1 -Server 192.168.1.10 -Name "office"
```

The script will:
1. Install `snapclient` via winget
2. Register a Task Scheduler task that starts on login and restarts on failure
3. Start it immediately

To stop/remove:
```powershell
Stop-ScheduledTask -TaskName SnapcastClient
Unregister-ScheduledTask -TaskName SnapcastClient -Confirm:$false
```

---

## Verifying the node is connected

Once the script finishes, go to `#spotify-chat` in Discord and type:

```
list rooms
```

The new node should appear with its name, volume, and connection status. If it doesn't show up within 30 seconds, check the logs (see platform sections above).

---

## Controlling volume from Discord

```
set <name> volume to 70
mute the <name>
unmute the <name>
```

Node names are fuzzy-matched, so "living room", "living-room", and "livingroom" all work.
