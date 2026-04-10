#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_MODULE="${API_MODULE:-api.main:app}"
API_PORT="${API_PORT:-8000}"
UVICORN_HOST="${UVICORN_HOST:-0.0.0.0}"

# Frontend config
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Ngrok config - choose which service to expose: "api", "frontend", or "both" (paid only)
# Default is "frontend"; backend routes are proxied in Vite config.
NGROK_MODE="${NGROK_MODE:-frontend}"
NGROK_API_PORT="${NGROK_API_PORT:-$API_PORT}"
NGROK_FRONTEND_PORT="${NGROK_FRONTEND_PORT:-$FRONTEND_PORT}"
NGROK_API_DOMAIN="${NGROK_API_DOMAIN:-}"
NGROK_FRONTEND_DOMAIN="${NGROK_FRONTEND_DOMAIN:-}"

for cmd in npm uvicorn ngrok; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
done

require_free_port() {
  local port="$1"
  local name="$2"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use ($name)."
    lsof -nP -iTCP:"$port" -sTCP:LISTEN
    echo "Stop the existing process, then run this script again."
    exit 1
  fi
}

require_free_port "$FRONTEND_PORT" "frontend"
require_free_port "$API_PORT" "api"

pids=()

cleanup() {
  for pid in "${pids[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}

trap cleanup INT TERM EXIT

echo "Starting frontend: npm run dev (port $FRONTEND_PORT)"
npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort &
pids+=("$!")

echo "Starting API: uvicorn $API_MODULE --reload --host $UVICORN_HOST --port $API_PORT"
uvicorn "$API_MODULE" --reload --host "$UVICORN_HOST" --port "$API_PORT" &
pids+=("$!")

# Start ngrok tunnels based on NGROK_MODE
if [ "$NGROK_MODE" = "api" ]; then
  if [ -n "$NGROK_API_DOMAIN" ]; then
    echo "Starting ngrok for API: ngrok http --domain $NGROK_API_DOMAIN $NGROK_API_PORT"
    ngrok http --domain "$NGROK_API_DOMAIN" "$NGROK_API_PORT" &
  else
    echo "Starting ngrok for API: ngrok http $NGROK_API_PORT"
    ngrok http "$NGROK_API_PORT" &
  fi
  pids+=("$!")
elif [ "$NGROK_MODE" = "frontend" ]; then
  if [ -n "$NGROK_FRONTEND_DOMAIN" ]; then
    echo "Starting ngrok for frontend: ngrok http --domain $NGROK_FRONTEND_DOMAIN $NGROK_FRONTEND_PORT"
    ngrok http --domain "$NGROK_FRONTEND_DOMAIN" "$NGROK_FRONTEND_PORT" &
  else
    echo "Starting ngrok for frontend: ngrok http $NGROK_FRONTEND_PORT"
    ngrok http "$NGROK_FRONTEND_PORT" &
  fi
  pids+=("$!")
elif [ "$NGROK_MODE" = "both" ]; then
  # Paid tier required for multiple tunnels
  echo "NOTE: Multiple tunnels require ngrok paid tier. Starting API tunnel only."
  if [ -n "$NGROK_API_DOMAIN" ]; then
    echo "Starting ngrok for API: ngrok http --domain $NGROK_API_DOMAIN $NGROK_API_PORT"
    ngrok http --domain "$NGROK_API_DOMAIN" "$NGROK_API_PORT" &
  else
    echo "Starting ngrok for API: ngrok http $NGROK_API_PORT"
    ngrok http "$NGROK_API_PORT" &
  fi
  pids+=("$!")
fi

echo ""
echo "Waiting for ngrok tunnel to be ready..."
sleep 5

echo ""
echo "=========================================="
echo "Services started:"
echo "  Frontend (local):     http://localhost:$FRONTEND_PORT"
echo "  API (local):          http://localhost:$API_PORT"
echo ""

# Get ngrok URL
if [ "$NGROK_MODE" = "api" ]; then
  NGROK_PORT="$NGROK_API_PORT"
else
  NGROK_PORT="$NGROK_FRONTEND_PORT"
fi
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | jq -r --arg addr "http://localhost:$NGROK_PORT" '.tunnels[] | select(.config.addr == $addr) | .public_url' 2>/dev/null | head -n1 || echo "")

if [ -n "$NGROK_URL" ]; then
  if [ "$NGROK_MODE" = "api" ]; then
    echo "  API (ngrok):          $NGROK_URL"
  elif [ "$NGROK_MODE" = "frontend" ]; then
    echo "  Frontend (ngrok):     $NGROK_URL"
  else
    echo "  ngrok:                $NGROK_URL"
  fi
fi
echo "=========================================="
echo ""

wait
