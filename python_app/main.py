import sys

from .app.bootstrap import run
from .app.main_window import MainWindow


def run_app() -> int:
    return int(run())


if __name__ == '__main__':
    sys.exit(run_app())
