#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# stop-dev.sh — Stop all dev services (macOS)
#
# On macOS: run this directly (./stop-dev.sh)
# On Windows: run stop-dev.ps1 instead (PowerShell)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.dev-pids"

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
GRAY='\033[0;90m'
NC='\033[0m'

echo -e "${YELLOW}Stopping dev services...${NC}"

# Kill saved PIDs
if [ -f "$PID_FILE" ]; then
    while IFS= read -r pid; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo -e "${GRAY}  Stopping PID $pid (+ children)...${NC}"
            # Kill process group (children too)
            pkill -P "$pid" 2>/dev/null || true
            kill "$pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
else
    echo -e "${GRAY}  No PID file found. Killing by port...${NC}"
fi

# Kill anything still on our ports (catches orphans)
for port in 8000 5173; do
    pids=$(lsof -ti ":$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        for pid in $pids; do
            echo -e "${GRAY}  Killing PID $pid on port $port${NC}"
            kill "$pid" 2>/dev/null || true
        done
    fi
done

# Clean up PID file
rm -f "$PID_FILE"

echo ""
echo -e "${GREEN}Done. All services stopped.${NC}"
echo ""
echo -e "${GRAY}Note: PostgreSQL and Redis are system services and were NOT stopped.${NC}"
