#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -z "${TRANSCRIPTOR_API_KEY:-}" ]; then
  echo "WARNING: TRANSCRIPTOR_API_KEY is not set. The service will run unauthenticated." >&2
fi

mkdir -p data

# shellcheck disable=SC1091
source venv/bin/activate
exec uvicorn src.api.main:app --host 127.0.0.1 --port 8000
