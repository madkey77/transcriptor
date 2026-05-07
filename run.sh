#!/usr/bin/env bash
# One-shot launcher: starts the Transcriptor backend + Cloudflare Tunnel.
# Press Ctrl+C once to shut everything down cleanly.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
LOG_DIR="$ROOT/.runtime"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
TUNNEL_LOG="$LOG_DIR/tunnel.log"

cleanup() {
  echo
  echo "Shutting down…"
  [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "${TUNNEL_PID:-}"  ] && kill "$TUNNEL_PID"  2>/dev/null || true
  wait 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT INT TERM

CLOUDFLARED="${CLOUDFLARED:-cloudflared}"
command -v "$CLOUDFLARED" >/dev/null 2>&1 || {
  echo "ERROR: cloudflared não encontrado no PATH. Instale com:" >&2
  echo "  curl -L -o ~/.local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x ~/.local/bin/cloudflared" >&2
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

echo "▶ Abrindo Cloudflare Quick Tunnel (logs → $TUNNEL_LOG)…"
: > "$TUNNEL_LOG"
"$CLOUDFLARED" tunnel --no-autoupdate --url http://localhost:8000 >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

# cloudflared imprime a URL no formato https://xxxx.trycloudflare.com
PUBLIC_URL=""
for _ in $(seq 1 60); do
  PUBLIC_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -1) || true
  [ -n "$PUBLIC_URL" ] && break
  sleep 1
done

if [ -z "$PUBLIC_URL" ]; then
  echo "ERROR: cloudflared não retornou URL. Últimas linhas:" >&2
  tail -20 "$TUNNEL_LOG" >&2
  exit 1
fi

cat <<BANNER

============================================================
  Transcriptor está no ar:
    $PUBLIC_URL
  Cole sua TRANSCRIPTOR_API_KEY na tela ao abrir.
  URL muda a cada restart (Quick Tunnel).
  Ctrl+C para encerrar tudo.
============================================================

BANNER

# Block until either process dies (then trap cleans up)
wait -n "$BACKEND_PID" "$TUNNEL_PID"
