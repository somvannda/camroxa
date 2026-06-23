#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start-dev.sh — Cross-platform dev environment launcher
#
# On macOS: run this directly (./start-dev.sh)
# On Windows: run start-dev.ps1 instead (PowerShell)
#
# Starts:
#   - Platform API (uvicorn on :8000)
#   - Admin Portal (vite on :5173)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.dev-pids"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN} CAMXORA Dev Environment (macOS)${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# ─── Cleanup leftover processes ─────────────────────────────────────────────
echo -e "${YELLOW}[CLEANUP] Checking for leftover processes...${NC}"

if [ -f "$PID_FILE" ]; then
    while IFS= read -r pid; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo -e "${GRAY}  Killing leftover PID $pid${NC}"
            kill "$pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

# Kill anything on our ports
for port in 8000 5173; do
    pids=$(lsof -ti ":$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        for pid in $pids; do
            echo -e "${GRAY}  Killing PID $pid on port $port${NC}"
            kill "$pid" 2>/dev/null || true
        done
    fi
done
sleep 1

# ─── Setup PATH ────────────────────────────────────────────────────────────
export PATH="$HOME/homebrew/Cellar/postgresql@16/16.14/bin:$HOME/local/python/bin:$HOME/local/node-v20.18.1-darwin-arm64/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONPATH="$ROOT"

# ─── Prerequisites check ───────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}[CHECK] Prerequisites${NC}"

PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}  Python: NOT FOUND${NC}"
    exit 1
fi
echo -e "${GRAY}  Python: $($PYTHON_CMD --version 2>&1)${NC}"

if command -v node &>/dev/null; then
    echo -e "${GRAY}  Node: $(node --version)${NC}"
else
    echo -e "${RED}  Node: NOT FOUND${NC}"
    exit 1
fi

# Check .env
if [ -f "$ROOT/platform_api/.env" ]; then
    echo -e "${GREEN}  .env: EXISTS${NC}"
else
    echo -e "${RED}  .env: MISSING${NC}"
fi

# Check PostgreSQL
if pg_isready -h localhost -p 5432 -q 2>/dev/null; then
    echo -e "${GREEN}  PostgreSQL: RUNNING${NC}"
else
    echo -e "${RED}  PostgreSQL: NOT RUNNING${NC}"
fi

# Check Redis
if nc -z localhost 6379 2>/dev/null; then
    echo -e "${GREEN}  Redis: RUNNING${NC}"
else
    echo -e "${YELLOW}  Redis: NOT RUNNING (API may start with degraded cache)${NC}"
fi

# ─── Start services ────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}Starting services...${NC}"
echo ""

# Start Platform API (output to terminal with prefix)
$PYTHON_CMD -u -m uvicorn platform_api.main:app \
    --reload --host 0.0.0.0 --port 8000 --log-level info \
    2>&1 | sed "s/^/[API] /" &
API_PID=$!
echo -e "${GRAY}  API started (PID $API_PID)${NC}"

# Start Admin Portal (output to terminal with prefix)
cd "$ROOT/admin_portal"
npm run dev 2>&1 | sed "s/^/[PORTAL] /" &
PORTAL_PID=$!
cd "$ROOT"
echo -e "${GRAY}  Portal started (PID $PORTAL_PID)${NC}"

# Save PIDs
echo "$API_PID" > "$PID_FILE"
echo "$PORTAL_PID" >> "$PID_FILE"

# Wait for services to be ready
echo ""
echo -e "${GRAY}  Waiting for services to start...${NC}"
sleep 2

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} All services running${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GRAY}  API:    http://localhost:8000${NC}"
echo -e "${GRAY}  Portal: http://localhost:5173${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services.${NC}"
echo -e "${GRAY}─────────────────────────────────────────${NC}"
echo ""

# Trap Ctrl+C to clean up
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping services...${NC}"
    kill "$API_PID" 2>/dev/null || true
    kill "$PORTAL_PID" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo -e "${GREEN}Done.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for background processes — logs stream to terminal in real time
wait
