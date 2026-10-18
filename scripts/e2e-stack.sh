#!/usr/bin/env bash
# Starts the whole app for the journey tests (E9): a fresh database, the API with recorded
# AI answers and the capture mailer, and the built web app. Used by CI and locally.
# On a Render preview the journeys run against the preview's URLs instead.
#
#   ADMIN_URL=postgresql://postgres:postgres@localhost:5432/postgres scripts/e2e-stack.sh
#   cd web && npx playwright test
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADMIN_URL="${ADMIN_URL:-postgresql://postgres:postgres@localhost:5432/postgres}"
DB="${E2E_DB:-boardroom_e2e}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-4173}"
PYTHON="${PYTHON:-python}"
RUN="${E2E_RUN_DIR:-$ROOT/.e2e}"
mkdir -p "$RUN"
rm -rf "$RUN/storage"

OWNER_URL="${ADMIN_URL%/*}/$DB"
psql "$ADMIN_URL" -qc "DROP DATABASE IF EXISTS \"$DB\" WITH (FORCE)" -c "CREATE DATABASE \"$DB\""

cd "$ROOT/backend"
MIGRATION_DATABASE_URL="$OWNER_URL" APP_DB_PASSWORD=br_login_e2e "$PYTHON" -m alembic upgrade head

export MIGRATION_DATABASE_URL="$OWNER_URL" APP_DB_PASSWORD=br_login_e2e
export ENVIRONMENT=development MAILER=capture DISPATCH_INLINE=true CONNECTORS_DEMO=true
export STORAGE_BACKEND=local STORAGE_ROOT="$RUN/storage"
export WEB_ORIGIN="http://localhost:$WEB_PORT" API_URL="http://localhost:$API_PORT"
# Recorded answers for the AI steps, so the journeys never call the live API (FR-13.2).
export SKILL1_REPLAY_DIR="$ROOT/backend/tests/fixtures/recorded" ANTHROPIC_API_KEY=""
nohup "$PYTHON" -m uvicorn boardroom.gateway.app:app --port "$API_PORT" > "$RUN/api.log" 2>&1 &
echo $! > "$RUN/api.pid"

cd "$ROOT/web"
VITE_API_URL="http://localhost:$API_PORT" npm run -s build > "$RUN/build.log" 2>&1
nohup npx vite preview --port "$WEB_PORT" --strictPort > "$RUN/web.log" 2>&1 &
echo $! > "$RUN/web.pid"

for _ in $(seq 60); do
  if curl -sf "http://localhost:$API_PORT/healthz" > /dev/null && curl -sf "http://localhost:$WEB_PORT" > /dev/null; then
    echo "API on $API_PORT, web on $WEB_PORT"
    exit 0
  fi
  sleep 1
done
echo "The app did not start. See $RUN/api.log and $RUN/web.log" >&2
exit 1
