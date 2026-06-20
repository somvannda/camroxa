import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
    force=True,
)

try:
    from .app.bootstrap import run
except ImportError:
    from python_app.app.bootstrap import run


raise SystemExit(run())
