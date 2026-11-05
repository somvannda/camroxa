"""The music web deploy must never restart Next.js without a real build.

Incident this pins: `camxora-music` was restarted with no `.next` directory
(`Could not find a production build`) and systemd retried it 6555 times while
nginx served connection-refused/502 for music.camxora.com.

The script must build first, verify BUILD_ID + prerender-manifest, and only
then restart; a failed build restores the previous `.next` and exits 1.
"""

from __future__ import annotations

from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parents[2] / "scripts" / "deploy"
SCRIPT = DEPLOY_DIR / "sync_music_web_production.py"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_build_runs_before_the_restart() -> None:
    text = _text()
    build = text.index("npm run build")
    build_id = text.index("test -s .next/BUILD_ID")
    restart = text.index("systemctl restart camxora-music")
    assert build < build_id < restart


def test_failed_build_restores_the_previous_build_and_exits() -> None:
    text = _text()
    assert "mv .next .next.prev" in text
    assert "MUSIC_WEB_BUILD_FAILED" in text
    assert "mv .next.prev .next" in text
    # Any destructive removal must happen only in the failed-build branch,
    # never before the build.
    assert text.index("rm -rf .next\n") > text.index("npm run build")


def test_missing_build_blocks_startup_and_caps_the_restart_loop() -> None:
    text = _text()
    assert "build-guard.conf" in text
    assert "ExecStartPre=" in text
    assert "missing .next/BUILD_ID" in text
    assert "StartLimitBurst=5" in text
    assert "Restart=on-failure" in text
