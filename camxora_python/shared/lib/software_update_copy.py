"""User-facing copy helpers for desktop software updates."""

from __future__ import annotations

import re

_HEADER_RE = re.compile(r"^#{1,6}\s+")
_BULLET_RE = re.compile(r"^[-*•]\s+")
_VERSION_BANNER_RE = re.compile(
    r"^(?:Camxora\s+)?\[?\d+\.\d+(?:\.\d+)?\]?\s*[-–—].*$",
    re.IGNORECASE,
)
_DATE_ONLY_RE = re.compile(
    r"^(?:"
    r"January|February|March|April|May|June|July|August|September|October|November|December"
    r")\s+\d{1,2},\s+\d{4}$|"
    r"^\d{4}-\d{2}-\d{2}$",
    re.IGNORECASE,
)
_SECTION_TITLE_RE = re.compile(
    r"^(?:what['’]?s\s+new|fixed|changed|added|removed|summary|product\s+impact|technical\s+impact)$",
    re.IGNORECASE,
)
_CODEY_RE = re.compile(
    r"(clearContents|removeCellWidget|app[_-]version\.txt|Meipass|_internal|pyinstaller)",
    re.IGNORECASE,
)
_PAREN_CODEY_RE = re.compile(
    r"\([^)]*(?:clearContents|removeCellWidget|app[_-]version\.txt)[^)]*\)",
    re.IGNORECASE,
)

# --- Gate titles -----------------------------------------------------------
TITLE_REQUIRED = "Update required"
TITLE_AVAILABLE = "Update available"
TITLE_DOWNLOADING = "Downloading update"
TITLE_INSTALLING = "Installing update"
TITLE_STARTING_INSTALLER = "Starting installer"
TITLE_FINISHING = "Finishing update"

# --- Actions ---------------------------------------------------------------
BUTTON_INSTALL = "Install update"
BUTTON_RETRY = "Try again"

# --- Body / status ---------------------------------------------------------
STATUS_PREPARING = "Preparing update…"
STATUS_STARTING_DOWNLOAD = "Starting download…"
STATUS_PREPARING_INSTALLER = "Preparing installer…"
STATUS_STARTING_INSTALLER = "Starting installer…"
STATUS_INSTALLING = "Installing update…"
STATUS_DOWNLOAD_COMPLETE = "Download complete. Starting installer…"
STATUS_FAILED_DEFAULT = "The update could not be installed. Please try again."
STATUS_PREVIOUS_FAILED = "The previous update did not finish. Please try again."
STATUS_PREVIOUS_FAILED_DETAIL = (
    "The previous update did not finish. If an installer window is still open, "
    "wait for it to complete — otherwise try again."
)
STATUS_STILL_OLD_VERSION = (
    "Installation finished, but this application is still on the previous version. "
    "Please try again."
)

SUMMARY_MANDATORY = (
    "A required update must be installed before you can continue.\n"
    "The application will close briefly to complete installation."
)

STATUS_CLOSING = (
    "The application is closing so the installer can update files. "
    "Please wait until installation finishes. This may take a few minutes."
)

STATUS_FINISHING = (
    "Installation is still in progress. Please wait for the installer to finish "
    "before reopening the application."
)

STATUS_FINISHING_SHORT = (
    "Installation is still in progress. Please wait for the installer to finish…"
)


def format_update_summary(*, required_version: str, current_version: str) -> str:
    # Versions live on the muted meta row; body stays outcome-only.
    _ = (required_version, current_version)
    return SUMMARY_MANDATORY


def format_version_row(*, required_version: str, current_version: str, mandatory: bool) -> str:
    required = str(required_version or "").strip() or "—"
    current = str(current_version or "").strip() or "—"
    label = "Required" if mandatory else "Available"
    return f"{label} {required}  ·  Current {current}"


def format_download_progress(*, percent: int | None = None, megabytes: float | None = None) -> str:
    if percent is not None:
        return f"Downloading update… {int(percent)}%"
    if megabytes is not None:
        return f"Downloading update… {megabytes:.1f} MB"
    return "Downloading update…"


def format_whats_new(release_notes: str, *, max_bullets: int = 8, max_chars: int = 110) -> list[str]:
    """Turn admin release notes into short, user-facing bullets."""
    text = str(release_notes or "").replace("\r\n", "\n").strip()
    if not text:
        return []

    bullets: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if _VERSION_BANNER_RE.match(line):
            continue
        if _HEADER_RE.match(line):
            continue
        line = _BULLET_RE.sub("", line).strip()
        line = _HEADER_RE.sub("", line).strip()
        line = _PAREN_CODEY_RE.sub("", line).strip(" -–—")
        if not line or _CODEY_RE.search(line):
            continue
        if _VERSION_BANNER_RE.match(line) or _DATE_ONLY_RE.match(line) or _SECTION_TITLE_RE.match(line):
            continue
        if len(line) > max_chars:
            line = line[: max_chars - 1].rstrip() + "…"
        if line not in bullets:
            bullets.append(line)
        if len(bullets) >= max_bullets:
            break

    if bullets:
        return bullets

    # Fallback: first non-empty paragraph, shortened — skip metadata-only notes.
    paragraph = " ".join(text.split())
    if (
        not paragraph
        or _CODEY_RE.search(paragraph)
        or _VERSION_BANNER_RE.match(paragraph)
        or _DATE_ONLY_RE.match(paragraph)
        or _SECTION_TITLE_RE.match(paragraph)
    ):
        return []
    if len(paragraph) > max_chars:
        paragraph = paragraph[: max_chars - 1].rstrip() + "…"
    return [paragraph]
