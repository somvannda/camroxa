"""Embedded chrome SVGs used when packaged resource files are unavailable."""

from __future__ import annotations

# Keep in sync with files under resources/.
APP_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#7c3aed"/>
      <stop offset="1" stop-color="#a855f7"/>
    </linearGradient>
  </defs>
  <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#lg)"/>
  <g fill="#ffffff">
    <rect x="17" y="27" width="5" height="10" rx="2.5"/>
    <rect x="25.5" y="20" width="5" height="24" rx="2.5"/>
    <rect x="34" y="16" width="5" height="32" rx="2.5"/>
    <rect x="42.5" y="24" width="5" height="16" rx="2.5"/>
  </g>
</svg>
"""

WINDOW_MINIMIZE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M5 12h14"/>
</svg>
"""

WINDOW_MAXIMIZE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="15 3 21 3 21 9"/>
  <polyline points="9 21 3 21 3 15"/>
  <line x1="21" x2="14" y1="3" y2="10"/>
  <line x1="3" x2="10" y1="21" y2="14"/>
</svg>
"""

WINDOW_CLOSE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M18 6 6 18"/>
  <path d="m6 6 12 12"/>
</svg>
"""

CHROME_SVG_BY_NAME: dict[str, str] = {
    "app-logo.svg": APP_LOGO_SVG,
    "window-minimize.svg": WINDOW_MINIMIZE_SVG,
    "window-maximize.svg": WINDOW_MAXIMIZE_SVG,
    "window-close.svg": WINDOW_CLOSE_SVG,
}
