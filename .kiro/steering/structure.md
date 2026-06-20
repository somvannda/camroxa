# Project Structure

```
MusicGenerator/
├── python_app/              # Desktop application (PyQt6)
│   ├── app/                 # Application shell & main window
│   │   ├── bootstrap.py     # Entry point (QApplication setup, theme)
│   │   ├── main_window.py   # Main window (being decomposed)
│   │   ├── signal_router.py # Qt signal routing
│   │   ├── ui_bus.py        # Cross-component event bus
│   │   └── *_handlers.py    # UI event handler groups
│   ├── features/            # Feature modules (coordinator pattern)
│   │   ├── ports.py         # Shared Protocol interfaces for DI
│   │   ├── auto_video/      # Auto video generation pipeline
│   │   ├── image/           # Image generation feature
│   │   ├── merge/           # Video merge/reel creation
│   │   ├── music/           # Music generation feature
│   │   ├── progress/        # Progress tracking coordinator
│   │   ├── profiles/        # Channel profile management
│   │   ├── templates/       # Video template management
│   │   ├── video_export/    # Video export pipeline
│   │   ├── video_workspace/ # Video preview/editing
│   │   └── youtube/         # YouTube upload feature
│   ├── design_system/       # UI design tokens + QSS generation
│   │   ├── tokens.py        # Frozen dataclass token definitions
│   │   ├── qss_generator.py # Token → QSS stylesheet compiler
│   │   ├── widgets/         # Reusable styled widget classes
│   │   └── layouts/         # Standard layout patterns
│   ├── services/            # External service integrations
│   ├── database/            # PostgreSQL persistence layer
│   ├── models/              # Domain models & types
│   ├── views/               # UI views (page controllers + views)
│   │   ├── components/      # Reusable UI components
│   │   └── helpers/         # View utility functions
│   ├── visualizer/          # Spectrum/particle GPU renderer
│   ├── utils/               # Shared utilities
│   └── tests/               # Test suite
│
├── platform_api/            # Backend API (FastAPI)
│   ├── main.py              # App factory + lifespan
│   ├── config.py            # Pydantic Settings
│   ├── dependencies.py      # FastAPI DI wiring
│   ├── exceptions.py        # Error hierarchy
│   ├── models/              # Domain models, enums, Pydantic schemas
│   ├── ports/               # Protocol interfaces (dependency inversion)
│   ├── middleware/           # Auth, rate limiting, audit
│   ├── routers/             # HTTP route handlers
│   ├── services/            # Business logic layer
│   ├── repositories/        # Database access layer
│   ├── clients/             # External API HTTP clients
│   ├── migrations/          # Alembic migrations
│   └── tests/               # Test suite
│
├── admin_portal/            # Admin web UI (React + Vite)
│   ├── src/
│   │   ├── components/      # UI components (shadcn/ui pattern)
│   │   ├── pages/           # Route page components
│   │   ├── hooks/           # Custom React hooks
│   │   ├── lib/             # Utilities (cn(), API client)
│   │   ├── types/           # TypeScript type definitions
│   │   └── styles/          # Global styles
│   └── tests/               # Test suite
│
├── archive/                 # Archived Electron/React app (legacy)
├── tools/                   # Build utilities (icon generation)
├── build/                   # PyInstaller build output
├── MusicGenerator.spec      # PyInstaller spec file
└── start-dev.ps1            # Starts API + Portal dev servers
```

## Architecture Patterns

### Desktop App — Coordinator Pattern
- Features are isolated into `features/<name>/coordinator.py`
- Coordinators receive dependencies via constructor injection (Protocol-based ports)
- No direct Qt imports in coordinators — UI interaction through callable ports
- Views are separated from controllers (`views/<name>_view.py` + `views/<name>_page_controller.py`)
- The main window is being decomposed into feature coordinators

### Platform API — Layered Architecture
- **Transport** (routers) → **Application** (services) → **Domain** (models) → **Infrastructure** (repositories, clients)
- Ports define Protocol interfaces for dependency inversion
- FastAPI Depends() for DI wiring
- Auth/rate-limit implemented as route dependencies (not blanket middleware)
- Repository pattern with raw asyncpg for performance

### Admin Portal — Standard React SPA
- shadcn/ui component pattern (Radix primitives + CVA + Tailwind)
- TanStack Query for server state
- React Hook Form + Zod for form handling
- MSW for API mocking in tests

## Key Conventions

- **Python style**: Type annotations everywhere, mypy strict, ruff for linting
- **Naming**: snake_case for Python, camelCase/PascalCase for TypeScript
- **Testing**: Property-based testing (Hypothesis/fast-check) for correctness properties alongside unit tests
- **Error handling**: Structured error responses (code + message + optional details) in the API
- **Database**: Atomic operations for financial data (credits), optimistic concurrency where needed
