#!/usr/bin/env bash
set -euo pipefail

# ==============================
# Nova Agent Stopper
# ==============================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8080}"

# Load .env if exists (untuk ambil PORT yang benar)
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  PORT="${PORT:-8080}"
fi

echo "🛑 Stopping Nova Agent..."

stopped_any=false

# 1. Stop process yang listen di port Nova (uvicorn)
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "${PIDS}" ]]; then
    echo "   → Killing process on port $PORT (PID: $PIDS)"
    kill $PIDS 2>/dev/null || true
    sleep 0.5
    # Force kill jika masih hidup
    for pid in $PIDS; do
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
    stopped_any=true
  fi
elif command -v fuser >/dev/null 2>&1; then
  if fuser "$PORT/tcp" >/dev/null 2>&1; then
    echo "   → Killing process on port $PORT"
    fuser -k "$PORT/tcp" 2>/dev/null || true
    stopped_any=true
  fi
else
  # Fallback: pkill by process name
  if pgrep -f "uvicorn app.main:app" >/dev/null 2>&1; then
    echo "   → Killing uvicorn Nova Agent process"
    pkill -f "uvicorn app.main:app" || true
    stopped_any=true
  fi
fi

# 2. Stop cloudflared tunnel
if pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
  echo "   → Stopping cloudflared tunnel"
  pkill -f "cloudflared tunnel" || true
  stopped_any=true
fi

# 3. Stop ngrok
if pgrep -x "ngrok" >/dev/null 2>&1; then
  echo "   → Stopping ngrok"
  pkill -x "ngrok" || true
  stopped_any=true
fi

sleep 0.8

# Verifikasi
still_running=false
if command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    still_running=true
  fi
fi

if $still_running; then
  echo "⚠️  Masih ada proses di port $PORT. Coba jalankan lagi atau cek manual:"
  echo "   lsof -i :$PORT"
  exit 1
fi

if $stopped_any; then
  echo "✅ Nova Agent berhasil dihentikan."
else
  echo "ℹ️  Tidak ada proses Nova Agent yang sedang berjalan."
fi
