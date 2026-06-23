#!/usr/bin/env bash
# Booking-Agent launcher (macOS/Linux).
#   ./run.sh full      # backend (:8000) + Next.js frontend (:3000/:3001)  ← recommended
#   ./run.sh web       # backend API only on http://localhost:8000 (docs at /docs)
#   ./run.sh frontend  # Next.js dev server only (needs backend running)
#   ./run.sh setup     # install deps + seed the demo catalog
#   ./run.sh test      # run the test suite
#   ./run.sh fresh     # wipe the demo DB and re-seed (resets sold seats)
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cmd="${1:-full}"

setup() {
  [ -d "$root/.venv" ] || uv --directory "$root" venv --python 3.11
  uv --directory "$root" pip install -e ".[dev,api,llm]"
  uv --directory "$root" run booking-agent init-db
  uv --directory "$root" run booking-agent seed
}

case "$cmd" in
  setup) setup ;;
  test)  uv --directory "$root" run pytest -q ;;
  fresh) rm -f "$root/booking.db"; setup; echo "Demo data reset." ;;
  web)
    setup
    echo ""
    echo "  ==============================================="
    echo "   Backend API on  http://localhost:8000   (docs at /docs)"
    echo "  ==============================================="
    echo ""
    uv --directory "$root" run uvicorn booking_agent.api.app:app --reload --reload-dir "$root/src" --port 8000
    ;;
  frontend)
    [ -d "$root/frontend/node_modules" ] || (cd "$root/frontend" && npm install)
    echo "Next.js starting — open the URL it prints (http://localhost:3000 or :3001)."
    (cd "$root/frontend" && npm run dev)
    ;;
  full)
    setup
    [ -d "$root/frontend/node_modules" ] || (cd "$root/frontend" && npm install)
    "$root/.venv/bin/python" -m uvicorn booking_agent.api.app:app --port 8000 --host 127.0.0.1 &
    echo "Backend running on :8000 (pid $!). Starting Next.js — open the URL it prints."
    (cd "$root/frontend" && npm run dev)
    ;;
  *) echo "Usage: ./run.sh [full|web|frontend|setup|test|fresh]" ;;
esac
