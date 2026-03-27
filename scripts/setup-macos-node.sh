#!/usr/bin/env bash
# setup-macos-node.sh — Install and configure snapclient on a macOS node
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<you>/music-server/main/scripts/setup-macos-node.sh | bash -s -- --server <server-ip>
#   OR after cloning:
#   bash scripts/setup-macos-node.sh --server 192.168.1.10 --name "bedroom"
#
# Options:
#   --server <ip>    IP address of the Snapcast server (required)
#   --name <name>    Friendly name for this node (default: hostname)
#   --help           Show this message
#
# Requirements: Homebrew (https://brew.sh)

set -euo pipefail

SERVER_IP=""
NODE_NAME="$(hostname -s)"

usage() {
    sed -n '2,13p' "$0" | sed 's/^# //'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server) SERVER_IP="$2"; shift 2 ;;
        --name)   NODE_NAME="$2"; shift 2 ;;
        --help)   usage ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$SERVER_IP" ]]; then
    echo "Error: --server <ip> is required"
    exit 1
fi

echo "=== Snapcast Node Setup (macOS) ==="
echo "Server:    $SERVER_IP"
echo "Node name: $NODE_NAME"
echo ""

# ── 1. Install snapclient via Homebrew ──────────────────────────────────────
echo "[1/3] Installing snapclient via Homebrew..."
if ! command -v brew &>/dev/null; then
    echo "Error: Homebrew is not installed."
    echo "Install it from https://brew.sh, then re-run this script."
    exit 1
fi

brew install snapcast

# ── 2. Create a launchd plist for auto-start ────────────────────────────────
echo "[2/3] Installing launchd service..."

PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/com.snapcast.snapclient.plist"
SNAPCLIENT_BIN="$(brew --prefix)/bin/snapclient"

mkdir -p "$PLIST_DIR"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.snapcast.snapclient</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SNAPCLIENT_BIN</string>
        <string>--host</string>
        <string>$SERVER_IP</string>
        <string>--hostID</string>
        <string>$NODE_NAME</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/snapclient.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/snapclient.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load -w "$PLIST_FILE"

# ── 3. Verify ────────────────────────────────────────────────────────────────
echo "[3/3] Checking connection..."
sleep 2
if launchctl list | grep -q "com.snapcast.snapclient"; then
    echo ""
    echo "✓ snapclient is running and connected to $SERVER_IP"
    echo "  Node name: $NODE_NAME"
    echo "  Type 'list rooms' in #spotify-chat to confirm."
    echo ""
    echo "  To check logs:  tail -f /tmp/snapclient.log"
    echo "  To stop:        launchctl unload ~/Library/LaunchAgents/com.snapcast.snapclient.plist"
else
    echo ""
    echo "✗ snapclient failed to start. Check logs:"
    echo "  tail -f /tmp/snapclient.log"
    exit 1
fi
