# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Camxora desktop (camxora_python).

Build with scripts/build-desktop.ps1 (sandbox or production).
Bundles UI resources, factory video templates, SSL certs, glfw, and the full
GPU preview stack so end users never need pip.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

block_cipher = None

ROOT = Path(SPECPATH).resolve()
REPO_ROOT = ROOT.parent
ENV_FILE = os.environ.get("CAMXORA_ENV_FILE", ".env.sandbox")
env_path = ROOT / ENV_FILE
if not env_path.is_file():
    env_path = ROOT / ".env.sandbox.example"

datas = []
binaries = []
hiddenimports = []

if env_path.is_file():
    datas.append((str(env_path), "."))

resources_dir = ROOT / "resources"
# Bundle the whole tree, then pin critical chrome assets explicitly so a
# partial Analysis never ships without logo / window-control SVGs.
if resources_dir.is_dir():
    datas.append((str(resources_dir), "resources"))
for chrome_name in (
    "app-icon.ico",
    "app-logo.svg",
    "app-version.txt",
    "window-close.svg",
    "window-minimize.svg",
    "window-maximize.svg",
    "log-out.svg",
):
    chrome_path = resources_dir / chrome_name
    if chrome_path.is_file():
        datas.append((str(chrome_path), "resources"))

factory_templates = REPO_ROOT / "python_app" / "video_templates_local.json"
# Optional legacy sample catalog — not auto-loaded by the app; keep only if present.
if factory_templates.is_file():
    datas.append((str(factory_templates), "data"))

datas += collect_data_files("certifi")
binaries += collect_dynamic_libs("glfw")

# Native / data-heavy packages only. Avoid collect_all() on numpy / PIL / OpenGL /
# librosa — that walks every submodule and dominates Analysis time on rebuilds.
# PyInstaller hooks + import tracing cover the pure-Python surface.
for package in ("cv2", "moderngl", "pygame", "glfw", "glcontext"):
    try:
        datas += collect_data_files(package)
        binaries += collect_dynamic_libs(package)
    except Exception:
        pass
    hiddenimports.append(package)

# soundfile is a top-level module; natives live in _soundfile_data.
try:
    datas += collect_data_files("_soundfile_data")
    binaries += collect_dynamic_libs("_soundfile_data")
except Exception:
    pass
hiddenimports += ["soundfile", "_soundfile", "_soundfile_data"]

# OpenGL needs platform .dll/.pyd data; pull files without collect_all(OpenGL).
try:
    datas += collect_data_files("OpenGL")
    binaries += collect_dynamic_libs("OpenGL")
except Exception:
    pass
hiddenimports.append("OpenGL")

for package in ("app", "shared", "features", "visualizer", "database"):
    hiddenimports += collect_submodules(package)

hiddenimports += [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "PySide6.QtNetwork",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "httpx",
    "httpx._transports",
    "httpx._transports.default",
    "certifi",
    "pydantic",
    "cryptography",
    "websockets",
    "moderngl",
    "moderngl.context",
    "numpy",
    "PIL",
    "PIL.Image",
    "pygame",
    "glfw",
    "OpenGL",
    "OpenGL.GL",
    "librosa",
    "soundfile",
    "cv2",
    "visualizer.preview_widget",
    "visualizer.gpu_render",
    "visualizer.audio",
]

# Deduplicate while preserving order
seen: set[str] = set()
unique_hidden: list[str] = []
for name in hiddenimports:
    if name not in seen:
        seen.add(name)
        unique_hidden.append(name)
hiddenimports = unique_hidden

icon_candidates = [
    ROOT / "resources" / "app-icon.ico",
    ROOT / "resources" / "app.ico",
    REPO_ROOT / "python_app" / "assets" / "icons" / "app.ico",
    REPO_ROOT / "camxora" / "public" / "app.ico",
]
icon_path = next((path for path in icon_candidates if path.is_file()), None)
icon = str(icon_path) if icon_path is not None else None

a = Analysis(
    ["run_entry.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchvision",
        "torchaudio",
        "tensorflow",
        "transformers",
        "tkinter",
        "matplotlib",
        "PyQt5",
        "PyQt6",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Camxora",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Camxora",
)
