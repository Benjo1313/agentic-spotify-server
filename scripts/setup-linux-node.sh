#!/usr/bin/env bash
# setup-linux-node.sh — Install and configure snapclient on a Linux node
#
# Usage:
#   curl -fsSL http://<server-ip>:8080/scripts/setup-linux-node.sh | bash -s -- --server <server-ip>
#   OR after cloning the repo:
#   bash scripts/setup-linux-node.sh --server 192.168.1.10 --name "living-room"
#
# Options:
#   --server <ip>    IP address of the Snapcast server (required)
#   --name <name>    Friendly name for this node (default: hostname)
#   --help           Show this message

set -euo pipefail

SERVER_IP=""
NODE_NAME="$(hostname)"

usage() {
    sed -n '2,12p' "$0" | sed 's/^# //'
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

echo "=== Snapcast Node Setup ==="
echo "Server:    $SERVER_IP"
echo "Node name: $NODE_NAME"
echo ""

# ── 1. Install snapclient ────────────────────────────────────────────────────
echo "[1/4] Installing snapclient..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y snapclient
elif command -v dnf &>/dev/null; then
    sudo dnf install -y snapclient
elif command -v pacman &>/dev/null; then
    sudo pacman -Sy --noconfirm snapcast
else
    echo "Unsupported package manager. Install snapclient manually and re-run."
    exit 1
fi

# ── 2. Configure /etc/default/snapclient ────────────────────────────────────
echo "[2/4] Configuring snapclient..."
SNAPCLIENT_CONF=/etc/default/snapclient

# Find the first available ALSA output device
ALSA_DEVICE=$(aplay -l 2>/dev/null | awk '/^card [0-9]+:/ {
    match($0, /card ([0-9]+):.*device ([0-9]+):/, arr)
    if (arr[1] != "" && arr[2] != "") { print "hw:" arr[1] "," arr[2]; exit }
}')

if [[ -z "$ALSA_DEVICE" ]]; then
    echo "Warning: no ALSA device found. Defaulting to 'default'."
    ALSA_DEVICE="default"
fi

echo "    ALSA device: $ALSA_DEVICE"

sudo tee "$SNAPCLIENT_CONF" > /dev/null <<EOF
# Managed by setup-linux-node.sh
START_SNAPCLIENT=true
SNAPCLIENT_OPTS="--host $SERVER_IP --player alsa:device=$ALSA_DEVICE --hostID $NODE_NAME"
EOF

# ── 3. Enable and start the service ─────────────────────────────────────────
echo "[3/4] Enabling snapclient service..."
sudo systemctl daemon-reload
sudo systemctl enable --now snapclient

# ── 4. Verify connection ─────────────────────────────────────────────────────
echo "[4/4] Checking connection..."
sleep 2
if systemctl is-active --quiet snapclient; then
    echo ""
    echo "✓ snapclient is running and connected to $SERVER_IP"
    echo "  Node name: $NODE_NAME"
    echo "  The node should appear in Discord within a few seconds."
    echo "  Type 'list rooms' in #spotify-chat to confirm."
else
    echo ""
    echo "✗ snapclient failed to start. Check logs with:"
    echo "  journalctl -u snapclient -n 50"
    exit 1
fi
