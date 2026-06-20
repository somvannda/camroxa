# Tech Stack & Build

## Language & Runtime

- Python 3.11+ (desktop app and platform API)
- TypeScript (admin portal)
- Target OS: Windows (desktop app)

## Desktop App (`python_app/`)

| Category | Technology |
|----------|-----------|
| UI Framework | PyQt6 6.7.0 |
| GPU Rendering | ModernGL (OpenGL 3.3 Core) |
| Video Export | FFmpeg (external binary) |
| YouTube | google-api-python-client + OAuth2 |
| Database | PostgreSQL (psycopg2/asyncpg) |
| Packaging | PyInstaller |
| Design System | Custom token-based QSS generator |

## Platform API (`platform_api/`)

| Category | Technology |
|----------|-----------|
| Framework | FastAPI (async-first) |
| Server | Uvicorn |
| Database | PostgreSQL 15+ via asyncpg + SQLAlchemy async |
| Migrations | Alembic |
| Cache/Rate Limit | Redis (hiredis) |
| Auth | PyJWT + bcrypt (passlib) |
| HTTP Client | httpx |
| Validation | Pydantic v2 |

## Admin Portal (`admin_portal/`)

| Category | Technology |
|----------|-----------|
| Framework | React 18 |
| Build | Vite |
| Styling | Tailwind CSS + tailwindcss-animate |
| Components | Radix UI primitives + shadcn/ui pattern (CVA + clsx + tailwind-merge) |
| State | TanStack React Query |
| Forms | React Hook Form + Zod |
| HTTP | Axios |
| Routing | React Router v6 |
| Testing | Vitest + Testing Library + MSW + fast-check |

## Common Commands

### Desktop App
```bash
# Run the app
python -m python_app

# Run tests
cd python_app
pytest tests/ -q

# Type check
mypy .

# Lint
ruff check .
```

### Platform API
```bash
# Install (editable with dev deps)
cd platform_api
pip install -e ".[dev]"

# Run server (dev)
uvicorn platform_api.main:app --reload --host 0.0.0.0 --port 8000

# Run migrations
alembic upgrade head

# Run tests
pytest tests/ -q
```

### Admin Portal
```bash
cd admin_portal

# Dev server
npm run dev

# Build
npm run build

# Tests
npm run test

# Lint
npm run lint
```

### Full Dev Environment
```powershell
# Start both API and Portal
.\start-dev.ps1
```

## Testing Approach

- **Property-based testing** via Hypothesis (Python) and fast-check (TypeScript)
- **pytest** for Python (both apps); pytest-asyncio for async platform API tests
- **Vitest** for admin portal with jsdom environment
- **MSW** for API mocking in frontend tests
- mypy strict mode enabled for both Python packages
