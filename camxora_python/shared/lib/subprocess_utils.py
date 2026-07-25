"""Subprocess helpers — never flash a console window on Windows.

Packaged Camxora is a windowed (no-console) app. Any ffmpeg / ffprobe /
PowerShell / msiexec child must use these helpers so the OS does not open
a black console popup. Enterprise desktop policy: all tooling stays in-process
or fully hidden in the background.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any


def no_window_kwargs() -> dict[str, Any]:
    """Kwargs for subprocess.Popen / run / call / check_output on Windows."""
    if sys.platform != "win32":
        return {}

    kwargs: dict[str, Any] = {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
    }
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = startupinfo
    except Exception:
        pass
    return kwargs


def run_hidden(args: list[str] | tuple[str, ...] | str, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """subprocess.run with console suppression."""
    merged = {**no_window_kwargs(), **kwargs}
    return subprocess.run(args, **merged)


def popen_hidden(args: list[str] | tuple[str, ...] | str, **kwargs: Any) -> subprocess.Popen[Any]:
    """subprocess.Popen with console suppression + kill-on-parent-exit job."""
    merged = {**no_window_kwargs(), **kwargs}
    proc = subprocess.Popen(args, **merged)
    assign_to_job(proc)
    return proc


def popen_hidden_orphan(args: list[str] | tuple[str, ...] | str, **kwargs: Any) -> subprocess.Popen[Any]:
    """Hidden child that must outlive Camxora (software-update helpers).

    Unlike ``popen_hidden``, this is **not** assigned to the kill-on-close job
    object — otherwise quitting the app would abort the installer mid-flight.
    """
    merged = {**no_window_kwargs(), **kwargs}
    if sys.platform == "win32":
        flags = int(merged.get("creationflags") or 0)
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        merged["creationflags"] = flags
        # Detach stdin/stdout/stderr so the orphan is not tied to our console handles.
        merged.setdefault("stdin", subprocess.DEVNULL)
        merged.setdefault("stdout", subprocess.DEVNULL)
        merged.setdefault("stderr", subprocess.DEVNULL)
        merged.setdefault("close_fds", True)
    return subprocess.Popen(args, **merged)


def check_output_hidden(args: list[str] | tuple[str, ...] | str, **kwargs: Any) -> bytes | str:
    """subprocess.check_output with console suppression."""
    merged = {**no_window_kwargs(), **kwargs}
    return subprocess.check_output(args, **merged)


# ── Windows Job Object: auto-kill children when Camxora exits ────────────────

_job_handle = None


def ensure_job_object():
    """Create a Windows Job Object with KILL_ON_JOB_CLOSE."""
    global _job_handle
    if _job_handle is not None:
        return _job_handle
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
        _job_handle = job
        return _job_handle
    except Exception:
        return None


def assign_to_job(proc: subprocess.Popen[Any]) -> None:
    """Assign a child so Windows kills it if Camxora exits/crashes."""
    if sys.platform != "win32":
        return
    job = ensure_job_object()
    if job is None:
        return
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, int(proc.pid))
        if handle:
            kernel32.AssignProcessToJobObject(job, handle)
            kernel32.CloseHandle(handle)
    except Exception:
        pass


def terminate_job() -> None:
    """Terminate every process assigned to the Camxora job object."""
    global _job_handle
    if sys.platform != "win32" or _job_handle is None:
        return
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject(_job_handle, 1)
    except Exception:
        pass
