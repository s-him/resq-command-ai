#!/usr/bin/env bash
set -Eeuo pipefail

# Run from the cloned repository root: ./run.sh
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"

for cmd in python3 node npm; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    echo "Install Python 3, Node.js (18.18+ recommended), and npm, then rerun."
    exit 1
  fi
done

if [[ ! -f "$BACKEND_DIR/requirements.txt" || ! -f "$FRONTEND_DIR/package.json" ]]; then
  echo "ERROR: backend/requirements.txt or frontend/package.json not found."
  echo "Run this script from inside the cloned resq-command-ai repository."
  exit 1
fi

echo "==> Setting up Python virtual environment..."
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"

echo "==> Installing frontend dependencies..."
cd "$FRONTEND_DIR"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

# Create frontend environment file only if the project provides a template.
if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
fi

echo "==> Starting ResQ Command..."
echo "Backend:  http://127.0.0.1:8000"
echo "API docs: http://127.0.0.1:8000/docs"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop both servers."
echo

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo
  echo "Stopping servers..."
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$BACKEND_DIR"
  exec "$VENV_DIR/bin/python" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host 127.0.0.1 --port 5173
) &
FRONTEND_PID=$!

# Wait until either server exits; Ctrl+C triggers cleanup.
wait -n "$BACKEND_PID" "$FRONTEND_PID"
