#!/usr/bin/env bash
# One-shot launcher: starts the Transcriptor backend + ngrok tunnel.
# Press Ctrl+C once to shut everything down cleanly.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
LOG_DIR="$ROOT/.runtime"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
NGROK_LOG="$LOG_DIR/ngrok.log"

cleanup() {
  echo
  echo "Shutting down…"
  [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "${NGROK_PID:-}"   ] && kill "$NGROK_PID"   2>/dev/null || true
  wait 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT INT TERM

command -v ngrok >/dev/null 2>&1 || {
  echo "ERROR: ngrok não está instalado. Veja README → 'Exposing the service via ngrok'." >&2
  exit 1
}

[ -f "$BACKEND/.env" ] || {
  echo "ERROR: $BACKEND/.env não existe. Crie com TRANSCRIPTOR_API_KEY e HF_TOKEN antes." >&2
  exit 1
}

echo "▶ Subindo backend (logs → $BACKEND_LOG)…"
"$BACKEND/start.sh" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Wait until uvicorn is listening
for _ in $(seq 1 60); do
  curl -s -o /dev/null http://127.0.0.1:8000/ && break
  sleep 1
done
curl -s -o /dev/null http://127.0.0.1:8000/ || {
  echo "ERROR: backend não subiu. Últimas linhas do log:" >&2
  tail -20 "$BACKEND_LOG" >&2
  exit 1
}
echo "  ✓ backend pronto em http://127.0.0.1:8000"

echo "▶ Abrindo túnel ngrok (logs → $NGROK_LOG)…"
NGROK_DOMAIN="${NGROK_DOMAIN:-egret-awake-vaguely.ngrok-free.app}"
ngrok http --domain="$NGROK_DOMAIN" 8000 --log=stdout >"$NGROK_LOG" 2>&1 &
NGROK_PID=$!

# ngrok exposes its local API on :4040 once ready
PUBLIC_URL=""
for _ in $(seq 1 30); do
  PUBLIC_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null \
    | grep -oE 'https://[a-zA-Z0-9.-]+\.ngrok[a-zA-Z0-9.-]*' \
    | head -1) || true
  [ -n "$PUBLIC_URL" ] && break
  sleep 1
done

if [ -z "$PUBLIC_URL" ]; then
  echo "ERROR: ngrok não retornou URL. Confira:" >&2
  echo "  - 'ngrok config add-authtoken <token>' já foi rodado" >&2
  echo "  - últimas linhas: $(tail -5 "$NGROK_LOG")" >&2
  exit 1
fi

cat <<BANNER

============================================================
  Transcriptor está no ar:
    $PUBLIC_URL
  Cole sua TRANSCRIPTOR_API_KEY na tela ao abrir.
  Painel ngrok local:  http://127.0.0.1:4040
  Ctrl+C para encerrar tudo.
============================================================

BANNER

# Block until either process dies (then trap cleans up)
wait -n "$BACKEND_PID" "$NGROK_PID"
