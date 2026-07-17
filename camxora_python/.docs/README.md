# Camxora AI Development Kit

> **Version:** 1.2.0 (Draft)
> **Framework:** Python + PySide6 (Qt6)
> **Architecture:** Feature-First + MVVM + Clean Architecture
> **Status:** Phase 4 — Profile page (Dashboard ✅ complete)

---

# Implementation Status

| Phase | Status |
|-------|--------|
| 0 Foundation | ✅ Done |
| 1 Core shell | ✅ Done |
| 2 Auth + API | ✅ Done |
| **3 Dashboard** | **✅ Done** | [requirements](pages/03_DASHBOARD_REQUIREMENTS.md) |
| **4 Profile** | **⏳ Next** | spec pending |
| 5 Workflow | Sketch — spec pending |
| 6 Progress | Sketch — spec pending |
| 7+ Music | Done ✅ | [07_MUSIC_REQUIREMENTS.md](pages/07_MUSIC_REQUIREMENTS.md) |
| **8 Image** | **Done ✅** | [08_IMAGE_REQUIREMENTS.md](pages/08_IMAGE_REQUIREMENTS.md) |
| **9 Settings** | **Done ✅** | 8-tab workspace implemented |

**Strategy:** [Page-by-page migration](pages/00_PAGE_BY_PAGE_STRATEGY.md) — complete each shell page to 100% before the next.

See **[02_IMPLEMENTATION_STATUS.md](02_IMPLEMENTATION_STATUS.md)** for module inventory and route status.

---

# Overview

Camxora is a professional AI-powered desktop application that automates digital content creation from idea to publishing.

Unlike traditional desktop applications, Camxora is designed as a modular platform capable of generating, editing, managing, and publishing AI-generated media through reusable workflows and intelligent automation.

The goal is not simply to create software—it is to build a scalable ecosystem capable of supporting future AI providers, plugins, cloud synchronization, and enterprise-level workflows.

---

# Primary Goals

Camxora should provide a unified workspace for:

* AI Music Generation
* AI Image Generation
* AI Thumbnail Generation
* AI Video Generation
* Video Editing
* Audio Editing
* Timeline Editing
* Media Library
* Prompt Management
* Batch Processing
* Workflow Automation
* Social Media Publishing
* Analytics
* Plugin Marketplace
* User Management
* Licensing
* Background Automation

---

# Core Principles

Every part of Camxora follows these principles.

## 1. Modular

Every feature is independent.

Features should be removable, replaceable, and extendable without affecting unrelated modules.

---

## 2. Reusable

Never duplicate UI.

Never duplicate business logic.

Every reusable component belongs in the Shared library.

---

## 3. Maintainable

Readable code is more valuable than clever code.

The project should remain easy to understand even after years of development.

---

## 4. Scalable

The architecture must comfortably support:

* Hundreds of features
* Thousands of source files
* Multiple developers
* Multiple AI coding assistants
* Plugin ecosystem

---

## 5. Performance First

Camxora should always feel responsive.

Heavy processing must never block the user interface.

---

## 6. AI Friendly

Every folder, class, and component should be organized so AI coding assistants can understand the project quickly and generate consistent code.

---

# Technology Stack

## Language

* Python 3.13+

## UI

* PySide6 (Qt6)

## Styling

* Qt Style Sheets (QSS)

## Database

* SQLite
* SQLAlchemy

## Configuration

* Pydantic

## Logging

* Loguru

## Testing

* pytest

## Media

* FFmpeg
* OpenCV
* Pillow

---

# Project Architecture

Camxora follows a **Feature-First Architecture**.

Instead of organizing code by technical layers only, every business feature owns its own pages, widgets, services, workers, models, and resources.

Example:

```text
features/
    music/
    images/
    videos/
    workflow/
    uploader/
    analytics/
```

This keeps related code together and improves maintainability.

---

# Shared Layer

Only reusable components belong inside the Shared layer.

Examples:

* Buttons
* Cards
* Dialogs
* Tables
* Search Boxes
* Notifications
* Theme Manager
* Settings Manager
* Utility Functions

---

# Major Features

Current planned feature modules include:

* Dashboard
* Workflow
* Music
* Images
* Thumbnails
* Videos
* Video Editor
* Audio Editor
* Media Library
* Prompt Library
* Upload Manager
* Scheduler
* Analytics
* Plugins
* User Profile
* Licensing
* Settings
* Logs
* Notifications
* Help Center

Each feature owns its own implementation.

---

# Documentation Structure

The project documentation is divided into focused documents.

```text
.docs/

00_AI_SYSTEM_PROMPT.md          ← AI / master dev prompt
01_PROJECT_REQUIREMENTS.md      ← Full requirements + phase plan
02_IMPLEMENTATION_STATUS.md     ← Live progress (update each phase)
pages/                          ← **Per-page specs (page-by-page migration)**
  00_PAGE_BY_PAGE_STRATEGY.md
  03_DASHBOARD_PAGE_SPEC.md     ← Active
  README.md
02_PROJECT_VISION.md
03_TECH_STACK.md
04_PROJECT_ARCHITECTURE.md
05_FEATURE_ARCHITECTURE.md
06_UI_DESIGN_SYSTEM.md
07_COMPONENT_LIBRARY.md
08_DESIGN_TOKENS.md
09_NAVIGATION.md
10_EVENT_SYSTEM.md
11_THREADING.md
12_DATABASE.md
13_PLUGIN_SYSTEM.md
14_AI_PROVIDER_SYSTEM.md
15_MEDIA_PIPELINE.md
16_WORKFLOW_ENGINE.md
17_FILE_MANAGER.md
18_CODING_STANDARD.md
19_TESTING.md
20_DEPLOYMENT.md
21_PROMPT_LIBRARY.md
22_CONTRIBUTING.md
23_ROADMAP.md
24_AI_CONTEXT.md
```

---

# Development Workflow

Every new feature should follow this lifecycle:

1. Define requirements.
2. Create a feature specification.
3. Design reusable components.
4. Implement business logic.
5. Connect the UI.
6. Add background workers if needed.
7. Write tests.
8. Review architecture.
9. Update documentation.

---

# Folder Philosophy

A folder should represent a business capability, not simply a programming concept.

Good:

```text
features/music/
```

Avoid:

```text
services/
widgets/
models/
```

when those folders grow to contain unrelated functionality.

---

# AI Development Philosophy

AI coding assistants are considered first-class development tools.

All generated code must:

* Follow the documented architecture.
* Reuse existing components.
* Avoid duplication.
* Keep files small and focused.
* Separate UI from business logic.
* Follow Python and Qt best practices.
* Be production-ready.

Prototype-quality code is not acceptable.

---

# Long-Term Vision

Camxora is intended to evolve into a complete AI content creation platform supporting:

* Multiple AI providers
* Plugin marketplace
* Workflow automation
* Local AI models
* Cloud synchronization
* Team collaboration
* Enterprise deployment
* Cross-platform support

The architecture should allow these capabilities to be added without major rewrites.

---

# Versioning

Documentation follows semantic versioning.

Example:

* v1.0.0 — Initial release
* v1.1.0 — New feature documentation
* v2.0.0 — Major architectural revision

---

# Contributing

Every contributor, human or AI, must read the documentation before implementing new functionality.

Consistency is more valuable than speed.

Architecture is more important than individual implementation details.

Reusable software is preferred over quick solutions.
