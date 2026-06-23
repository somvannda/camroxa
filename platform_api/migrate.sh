#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# migrate.sh — Run Alembic migrations to sync database schema
#
# Usage:
#   ./migrate.sh              # Upgrade to latest (head)
#   ./migrate.sh current      # Show current migration version
#   ./migrate.sh history      # Show migration history
#   ./migrate.sh downgrade -1 # Roll back one migration
#
# Prerequisites:
#   - PostgreSQL running on localhost:5432
#   - Database 'platform_db' exists
#   - Python environment with platform_api[dev] installed
#   - .env file configured in platform_api/
#
# When you pull new code from git and there are new migrations, just run:
#   cd platform_api && ./migrate.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Resolve script directory (works regardless of where you call it from)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Add common homebrew/local python paths
export PATH="$HOME/homebrew/Cellar/postgresql@16/16.14/bin:$HOME/local/python/bin:$HOME/local/node-v20.18.1-darwin-arm64/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONPATH="$PROJECT_ROOT"

cd "$SCRIPT_DIR"

# Default action: upgrade to head
ACTION="${1:-upgrade}"

case "$ACTION" in
    current)
        echo "📍 Current migration version:"
        alembic current
        ;;
    history)
        echo "📜 Migration history:"
        alembic history --verbose
        ;;
    upgrade)
        TARGET="${2:-head}"
        echo "⬆️  Upgrading database to: $TARGET"
        alembic upgrade "$TARGET"
        echo "✅ Migration complete. Current version:"
        alembic current
        ;;
    downgrade)
        TARGET="${2:--1}"
        echo "⬇️  Downgrading database: $TARGET"
        alembic downgrade "$TARGET"
        echo "✅ Downgrade complete. Current version:"
        alembic current
        ;;
    stamp)
        TARGET="${2:-head}"
        echo "🔖 Stamping database at: $TARGET"
        alembic stamp "$TARGET"
        echo "✅ Stamped. Current version:"
        alembic current
        ;;
    *)
        echo "Usage: $0 [current|history|upgrade|downgrade|stamp] [target]"
        echo ""
        echo "Commands:"
        echo "  current              Show current migration version"
        echo "  history              Show full migration history"
        echo "  upgrade [target]     Upgrade to target (default: head)"
        echo "  downgrade [target]   Downgrade to target (default: -1)"
        echo "  stamp [target]       Stamp version without running migrations"
        exit 1
        ;;
esac
