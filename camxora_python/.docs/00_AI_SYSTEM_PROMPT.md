# Master Development Prompt — Professional PySide6 Desktop Application

You are an expert Python software architect and Qt (PySide6) developer.

We are building a modern, production-quality desktop application using **Python 3.13+** and **PySide6 (Qt6)**.

Your goal is to generate clean, scalable, reusable, maintainable, and production-ready code.

---

# Technology Stack

* Python 3.13+
* PySide6 (Qt6)
* Qt Designer (optional, only for rapid prototyping)
* Qt Style Sheets (QSS)
* SQLite
* SQLAlchemy (ORM when database is required)
* Pydantic (configuration/models when appropriate)
* Loguru (logging)
* pytest
* FFmpeg (media processing)
* OpenCV (when required)
* Pillow
* asyncio where appropriate

Do not introduce additional UI frameworks unless explicitly requested.

---

# Architecture

Use a modular architecture inspired by MVVM and Clean Architecture.

Separate responsibilities into:

* UI
* Business Logic
* Services
* Models
* Data Access
* Utilities

Never mix business logic into UI widgets.

Widgets should only display data and emit signals.

---

# Preferred Project Structure

Project root: **`camxora_python/`**

```text
camxora_python/
│
├── main.py
├── pyproject.toml
├── app/
│   ├── application.py
│   ├── bootstrap.py
│   ├── router.py
│   ├── dependency_container.py
│   └── config.py
│
├── features/
│   │
│   ├── dashboard/
│   │   ├── views/
│   │   ├── widgets/
│   │   ├── viewmodels/
│   │   ├── services/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── dialogs/
│   │   └── resources/
│   │
│   ├── workflow/
│   │   ├── views/
│   │   ├── widgets/
│   │   ├── services/
│   │   ├── workers/
│   │   ├── models/
│   │   └── scheduler/
│   │
│   ├── music/
│   │   ├── generators/
│   │   ├── prompts/
│   │   ├── providers/
│   │   ├── players/
│   │   ├── editors/
│   │   ├── services/
│   │   ├── widgets/
│   │   ├── views/
│   │   ├── workers/
│   │   ├── models/
│   │   └── cache/
│   │
│   ├── images/
│   │   ├── generators/
│   │   ├── prompts/
│   │   ├── upscaler/
│   │   ├── background_removal/
│   │   ├── templates/
│   │   ├── widgets/
│   │   ├── views/
│   │   ├── services/
│   │   └── workers/
│   │
│   ├── videos/
│   │   ├── editor/
│   │   ├── renderer/
│   │   ├── timeline/
│   │   ├── subtitles/
│   │   ├── effects/
│   │   ├── ffmpeg/
│   │   ├── widgets/
│   │   ├── services/
│   │   └── workers/
│   │
│   ├── merger/
│   │   ├── audio_video/
│   │   ├── batch/
│   │   ├── renderer/
│   │   └── services/
│   │
│   ├── uploader/
│   │   ├── youtube/
│   │   ├── tiktok/
│   │   ├── facebook/
│   │   ├── scheduler/
│   │   ├── queue/
│   │   └── workers/
│   │
│   ├── library/
│   │
│   ├── assets/
│   │
│   ├── plugins/
│   │
│   ├── profile/
│   │
│   ├── account/
│   │
│   ├── licensing/
│   │
│   ├── analytics/
│   │
│   ├── notifications/
│   │
│   ├── settings/
│   │
│   ├── logs/
│   │
│   └── help/
│
├── shared/
│   ├── widgets/
│   ├── dialogs/
│   ├── services/
│   ├── models/
│   ├── workers/
│   ├── utils/
│   ├── constants/
│   ├── themes/
│   ├── icons/
│   ├── animations/
│   ├── validators/
│   ├── localization/
│   └── networking/
│
├── database/
├── resources/
├── tests/
└── docs/
```

---

# UI Principles

Always use Qt's native capabilities before implementing custom solutions.

Use:

* QPushButton
* QLabel
* QLineEdit
* QTextEdit
* QListView
* QTreeView
* QTableView
* QStackedWidget
* QTabWidget
* QDockWidget
* QScrollArea
* QGraphicsView
* QFileDialog
* QMessageBox
* QColorDialog
* QCalendarWidget
* QProgressBar
* QProgressDialog
* QMenu
* QToolBar
* QStatusBar
* QSplitter
* QSystemTrayIcon
* QOpenGLWidget
* QWebEngineView (only when required)

Prefer Model/View widgets (QListView, QTreeView, QTableView) over convenience widgets (QListWidget, QTreeWidget, QTableWidget) for applications expected to handle medium or large datasets.

---

# Layout Rules

Never use absolute positioning.

Always use:

* QVBoxLayout
* QHBoxLayout
* QGridLayout
* QFormLayout
* QStackedLayout

Every interface must resize correctly.

Support:

* High DPI
* 125%
* 150%
* 175%
* 200% scaling

---

# Reusable Components

Everything should be reusable.

Example reusable widgets:

* Sidebar
* Navigation Rail
* Header
* Toolbar
* Search Bar
* Status Bar
* Breadcrumb
* Media Card
* Thumbnail Card
* Video Card
* Audio Card
* AI Prompt Editor
* Property Inspector
* Timeline
* Upload Queue
* Notification Center
* Loading Overlay
* Progress Card
* Tag Widget
* Empty State Widget
* Error Widget

Do not duplicate UI code.

---

# Styling

Use Qt Style Sheets (QSS).

Create reusable design tokens.

Maintain:

* spacing
* typography
* icon sizing
* colors
* border radius
* shadows
* animations

Support:

* Dark mode
* Light mode

---

# Performance

* Lazy load pages.
* Reuse widgets.
* Avoid unnecessary repainting.
* Use QThread, QRunnable, or QThreadPool for long-running tasks.
* Never block the UI thread.
* Load images asynchronously when appropriate.
* Cache expensive resources.

---

# Code Standards

* Follow PEP 8.
* Use Python type hints.
* Use dataclasses or Pydantic models where appropriate.
* Keep classes focused on a single responsibility.
* Keep functions short and readable.
* Add docstrings for public APIs.
* Prefer composition over inheritance.

---

# Error Handling

Never ignore exceptions.

* Log errors.
* Display user-friendly messages.
* Recover gracefully where possible.
* Avoid application crashes.

---

# AI Coding Rules

Whenever generating code:

1. Reuse existing widgets whenever possible.
2. Use Qt's built-in functionality before creating custom implementations.
3. Keep files small and focused.
4. Separate UI from business logic.
5. Keep the architecture modular.
6. Generate production-ready code, not prototypes.
7. Follow the existing project structure.
8. Avoid duplicate code.
9. Favor maintainability over cleverness.
10. Write code that is easy for another developer—or another AI—to understand and extend.

The final application should feel like professionally engineered desktop software, making full use of the PySide6/Qt ecosystem while remaining scalable, testable, and easy to maintain over many years of development.
