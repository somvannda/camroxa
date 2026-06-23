#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup-db.sh — Create the database and run all migrations from scratch
#
# Usage (on a fresh machine after git clone):
#   cd platform_api
#   pip install -e ".[dev]"
#   ./setup-db.sh
#
# This will:
#   1. Create the 'platform_db' database if it doesn't exist
#   2. Run all Alembic migrations to bring schema to latest
#
# Prerequisites:
#   - PostgreSQL installed and running on localhost:5432
#   - User 'postgres' accessible (or set DB_USER env var)
#   - Python environment with platform_api[dev] installed
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Add common paths
export PATH="$HOME/homebrew/Cellar/postgresql@16/16.14/bin:$HOME/local/python/bin:$HOME/local/node-v20.18.1-darwin-arm64/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONPATH="$PROJECT_ROOT"

DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-platform_db}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

cd "$SCRIPT_DIR"

echo "========================================="
echo " CAMXORA Database Setup"
echo "========================================="
echo ""

# Check PostgreSQL is running
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; then
    echo "❌ PostgreSQL is not running on $DB_HOST:$DB_PORT"
    echo "   Start it first, then re-run this script."
    exit 1
fi
echo "✅ PostgreSQL is running on $DB_HOST:$DB_PORT"

# Create database if it doesn't exist
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo "✅ Database '$DB_NAME' already exists"
else
    echo "📦 Creating database '$DB_NAME'..."
    createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
    echo "✅ Database '$DB_NAME' created"
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  No .env file found. Creating default..."
    cat > .env <<EOF
PLATFORM_DEBUG=true
PLATFORM_DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}
PLATFORM_REDIS_URL=redis://localhost:6379/0
PLATFORM_ENCRYPTION_MASTER_KEY=OK_LET_DO_THIS
PLATFORM_SLAI_API_BASE_URL=https://api.slai.shop
PLATFORM_DEEPSEEK_API_BASE_URL=https://api.deepseek.com
EOF
    echo "✅ Default .env created"
fi

# Run migrations
echo ""
echo "⬆️  Running all migrations..."
alembic upgrade head

echo ""
echo "========================================="
echo " ✅ Database setup complete!"
echo "========================================="
echo ""
echo "Current migration version:"
alembic current
echo ""
echo "You can now start the API with:"
echo "  uvicorn platform_api.main:app --reload --host 0.0.0.0 --port 8000"
