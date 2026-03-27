"""
One-time Spotify OAuth2 Authorization Code flow.

Run this script once to obtain a refresh token and store it in config/.env.

Usage:
    cd /home/benjo/Projects/music-server
    source .venv/bin/activate
    python scripts/spotify_auth.py
"""

import http.server
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import requests

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = " ".join([
    "user-modify-playback-state",
    "user-read-playback-state",
    "user-read-currently-playing",
    "user-read-recently-played",
])


def load_env(path: str) -> dict:
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip().strip('"')
    return env


def save_refresh_token(env_path: str, token: str) -> None:
    with open(env_path) as f:
        contents = f.read()

    if "SPOTIFY_REFRESH_TOKEN" in contents:
        lines = []
        for line in contents.splitlines():
            if line.startswith("SPOTIFY_REFRESH_TOKEN"):
                lines.append(f'SPOTIFY_REFRESH_TOKEN="{token}"')
            else:
                lines.append(line)
        new_contents = "\n".join(lines) + "\n"
    else:
        new_contents = contents.rstrip("\n") + f'\nSPOTIFY_REFRESH_TOKEN="{token}"\n'

    with open(env_path, "w") as f:
        f.write(new_contents)


def main():
    env_path = os.path.join(os.path.dirname(__file__), "../config/.env")
    env_path = os.path.abspath(env_path)

    env = load_env(env_path)
    client_id = env.get("SPOTIFY_CLIENT_ID")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("ERROR: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in config/.env")
        sys.exit(1)

    state = secrets.token_hex(16)
    auth_code = None
    error_received = None

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            nonlocal auth_code, error_received
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if params.get("state", [None])[0] != state:
                error_received = "State mismatch — possible CSRF"
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch. Close this window.")
                return

            if "error" in params:
                error_received = params["error"][0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error: {error_received}".encode())
                return

            auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Auth successful! You can close this window.")

    server = http.server.HTTPServer(("127.0.0.1", 8888), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&scope={urllib.parse.quote(SCOPES)}"
        f"&state={state}"
    )

    print(f"\nOpening browser for Spotify authorization...")
    print(f"If the browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    thread.join(timeout=120)

    if error_received:
        print(f"ERROR: {error_received}")
        sys.exit(1)

    if not auth_code:
        print("ERROR: Timed out waiting for authorization.")
        sys.exit(1)

    # Exchange code for tokens
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        auth=(client_id, client_secret),
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    resp.raise_for_status()
    tokens = resp.json()
    refresh_token = tokens["refresh_token"]

    save_refresh_token(env_path, refresh_token)
    print(f"Refresh token saved to {env_path}")
    print("Done.")


if __name__ == "__main__":
    main()
