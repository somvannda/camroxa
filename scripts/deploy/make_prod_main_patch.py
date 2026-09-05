#!/usr/bin/env python3
"""Generate prod main.py + streaming auto-retry startup insertion (additive).

Takes the actual prod main.py pulled earlier and inserts only the auto-retry
loop block, so prod never receives unrelated main-era changes.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / ".dbg" / "prod-stream-src" / "platform_api__main.py"
OUT = ROOT / ".dbg" / "prod-main-auto-retry.py"

ANCHOR = '''            logger.info("Web music subscription maintenance loop started (every 15 minutes).")
        except Exception as exc:
            logger.warning("Web music subscription maintenance not configured (non-fatal): %s", exc)

        # --- Warm Key Pool Redis cache ---
'''

INSERT = '''            logger.info("Web music subscription maintenance loop started (every 15 minutes).")
        except Exception as exc:
            logger.warning("Web music subscription maintenance not configured (non-fatal): %s", exc)

        # --- Streaming upload auto-retry (B2 capture assurance) ---
        try:
            from platform_api.services import streaming_upload_service as _streaming_svc

            if not getattr(_streaming_svc, "_AUTO_RETRY_ENABLED", True):
                logger.info("Streaming upload auto-retry is disabled by env.")
            else:
                auto_retry_task = asyncio.create_task(
                    _streaming_svc.run_streaming_auto_retry_loop(db_pool),
                    name="streaming-auto-retry",
                )
                logger.info("Streaming upload auto-retry loop started.")
        except Exception as exc:
            logger.warning("Streaming upload auto-retry loop not started (non-fatal): %s", exc)

        # --- Warm Key Pool Redis cache ---
'''


def main() -> int:
    text = PROD.read_text(encoding="utf-8")
    count = text.count(ANCHOR)
    if count != 1:
        raise SystemExit(f"Expected exactly 1 anchor match, found {count} in {PROD.name}")
    OUT.write_text(text.replace(ANCHOR, INSERT), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    raise SystemExit(main())
