#!/usr/bin/env bash
# Open a free Cloudflare quick-tunnel to the local OLM bridge so the deployed
# dashboard at https://hildieleyser.github.io/auracle/ can connect from anywhere.
#
#   1. start the bridge:    python server/ovlm_bridge_server.py
#   2. start the tunnel:    ./viz/tunnel.sh
#   3. copy the printed     https://*.trycloudflare.com URL
#   4. paste it into the    Dashboard → Source sheet
#
# WebSocket upgrades pass straight through — no extra config needed.

set -euo pipefail

PORT="${BRIDGE_PORT:-8765}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not installed."
  echo
  echo "  brew install cloudflared      # macOS"
  echo "  https://github.com/cloudflare/cloudflared#installing-cloudflared"
  exit 1
fi

if ! lsof -i ":${PORT}" >/dev/null 2>&1; then
  echo "Nothing listening on :${PORT} — start the bridge first:"
  echo "  python server/ovlm_bridge_server.py"
  echo
  echo "(Continuing anyway; the tunnel will be ready once the bridge starts.)"
  echo
fi

echo "Opening Cloudflare quick tunnel → http://localhost:${PORT}"
echo "Look for a https://*.trycloudflare.com URL in the output below."
echo

exec cloudflared tunnel --url "http://localhost:${PORT}"
