"""Classify "the child stopped reading our pipe" write failures.

Windows reports a dead child pipe as ``EINVAL (22)`` instead of ``EPIPE (32)``,
so a ``BrokenPipeError``-only check misses the most common ffmpeg crash report
(``[Errno 22] Invalid argument``) and misdiagnoses it as a bad argument.
"""

from __future__ import annotations

import errno

_PIPE_CLOSED_ERRNOS = frozenset({errno.EPIPE, errno.EINVAL})


def is_pipe_closed_error(exc: BaseException) -> bool:
    """True when ``exc`` means the child process stopped reading its stdin pipe."""
    if isinstance(exc, BrokenPipeError):
        return True
    if isinstance(exc, OSError):
        return exc.errno in _PIPE_CLOSED_ERRNOS
    return False


def os_error_suffix(exc: BaseException) -> str:
    """``", winerror 232"`` when Windows exposed one — helps support triage."""
    win = getattr(exc, "winerror", None)
    return f", winerror {win}" if win else ""
