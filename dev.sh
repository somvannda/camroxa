#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# dev.sh — Universal dev launcher (detects OS and runs the right script)
#
# Usage:
#   ./dev.sh start    — Start all dev services
#   ./dev.sh stop     — Stop all dev services
#   ./dev.sh          — Same as start
#
# On macOS: uses start-dev.sh / stop-dev.sh (bash)
# On Windows (Git Bash / WSL): uses start-dev.ps1 / stop-dev.ps1 (PowerShell)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-start}"

case "$(uname -s)" in
    Darwin*)
        # macOS
        case "$ACTION" in
            start)
                exec "$ROOT/start-dev.sh"
                ;;
            stop)
                exec "$ROOT/stop-dev.sh"
                ;;
            *)
                echo "Usage: $0 [start|stop]"
                exit 1
                ;;
        esac
        ;;
    MINGW*|MSYS*|CYGWIN*)
        # Windows (Git Bash / MSYS2 / Cygwin)
        case "$ACTION" in
            start)
                echo "Detected Windows — launching PowerShell start-dev.ps1..."
                powershell.exe -ExecutionPolicy Bypass -File "$ROOT/start-dev.ps1"
                ;;
            stop)
                echo "Detected Windows — launching PowerShell stop-dev.ps1..."
                powershell.exe -ExecutionPolicy Bypass -File "$ROOT/stop-dev.ps1"
                ;;
            *)
                echo "Usage: $0 [start|stop]"
                exit 1
                ;;
        esac
        ;;
    Linux*)
        # Linux / WSL
        if grep -qi microsoft /proc/version 2>/dev/null; then
            # WSL — use PowerShell
            case "$ACTION" in
                start)
                    echo "Detected WSL — launching PowerShell start-dev.ps1..."
                    powershell.exe -ExecutionPolicy Bypass -File "$(wslpath -w "$ROOT/start-dev.ps1")"
                    ;;
                stop)
                    echo "Detected WSL — launching PowerShell stop-dev.ps1..."
                    powershell.exe -ExecutionPolicy Bypass -File "$(wslpath -w "$ROOT/stop-dev.ps1")"
                    ;;
                *)
                    echo "Usage: $0 [start|stop]"
                    exit 1
                    ;;
            esac
        else
            # Native Linux — use the bash scripts (same as macOS)
            case "$ACTION" in
                start)
                    exec "$ROOT/start-dev.sh"
                    ;;
                stop)
                    exec "$ROOT/stop-dev.sh"
                    ;;
                *)
                    echo "Usage: $0 [start|stop]"
                    exit 1
                    ;;
            esac
        fi
        ;;
    *)
        echo "Unsupported OS: $(uname -s)"
        echo "Run start-dev.ps1 (Windows) or start-dev.sh (macOS/Linux) directly."
        exit 1
        ;;
esac
