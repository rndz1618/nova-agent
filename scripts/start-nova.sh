#!/usr/bin/env bash
set -euo pipefail

# ==============================
# Nova Agent Launcher
# ==============================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Load .env if exists
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  echo "❌ File .env tidak ditemukan. Copy dari .env.example dulu:"
  echo "   cp .env.example .env && nano .env"
  exit 1
fi

# Validate required vars
if [[ -z "${NOVA_API_KEY:-}" || "${NOVA_API_KEY}" == "change-me-to-a-very-long-random-string-at-least-32-chars" ]]; then
  echo "❌ NOVA_API_KEY belum di-set dengan benar di .env"
  exit 1
fi

if [[ -z "${REPO_PATH:-}" ]]; then
  echo "❌ REPO_PATH belum di-set di .env"
  exit 1
fi

PORT="${PORT:-8080}"
HOST="${HOST:-127.0.0.1}"
TUNNEL_PROVIDER="${TUNNEL_PROVIDER:-cloudflare}"

echo "🚀 Starting Nova Agent..."
echo "   Repo   : $REPO_PATH"
echo "   Listen : http://${HOST}:${PORT}"
echo "   Tunnel : $TUNNEL_PROVIDER"
echo ""

# Create logs dir
mkdir -p logs

# Activate venv if exists
if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Start uvicorn in background
uvicorn app.main:app --host "$HOST" --port "$PORT" --log-level info &
UVICORN_PID=$!

cleanup() {
  echo ""
  echo "🛑 Stopping Nova Agent..."
  kill "$UVICORN_PID" 2>/dev/null || true
  if [[ -n "${TUNNEL_PID:-}" ]]; then
    kill "$TUNNEL_PID" 2>/dev/null || true
  fi
  wait "$UVICORN_PID" 2>/dev/null || true
  echo "✅ Stopped."
}
trap cleanup EXIT INT TERM

# Give server a moment to start
sleep 1.5

# ---------- Tunnel ----------
case "$TUNNEL_PROVIDER" in
  cloudflare)
    if command -v cloudflared >/dev/null 2>&1; then
      if [[ -n "${CLOUDFLARE_TUNNEL_NAME:-}" ]]; then
        echo "🌐 Starting Cloudflare named tunnel: $CLOUDFLARE_TUNNEL_NAME"
        cloudflared tunnel run "$CLOUDFLARE_TUNNEL_NAME" &
      else
        echo "🌐 Starting Cloudflare quick tunnel (trycloudflare.com)..."
        cloudflared tunnel --url "http://${HOST}:${PORT}" &
      fi
      TUNNEL_PID=$!
    else
      echo "⚠️  cloudflared tidak ditemukan. Install dulu: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
      echo "   Server tetap jalan di localhost saja."
    fi
    ;;
  ngrok)
    if command -v ngrok >/dev/null 2>&1; then
      if [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
        ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true
      fi
      echo "🌐 Starting ngrok tunnel..."
      if [[ -n "${NGROK_DOMAIN:-}" ]]; then
        ngrok http --domain="$NGROK_DOMAIN" "$PORT" &
      else
        ngrok http "$PORT" &
      fi
      TUNNEL_PID=$!
      sleep 2
      echo "   Cek URL publik di: http://127.0.0.1:4040"
    else
      echo "⚠️  ngrok tidak ditemukan. Install dari https://ngrok.com"
    fi
    ;;
  none)
    echo "ℹ️  Tunnel dimatikan (TUNNEL_PROVIDER=none). Hanya accessible dari localhost."
    ;;
  *)
    echo "❌ TUNNEL_PROVIDER tidak dikenal: $TUNNEL_PROVIDER (pilih: cloudflare | ngrok | none)"
    exit 1
    ;;
esac

echo ""
echo "✅ Nova Agent running. Tekan Ctrl+C untuk stop."
echo "   Health check: curl http://${HOST}:${PORT}/health"
echo ""

# Wait for uvicorn
wait "$UVICORN_PID"
