"""Shared subprocess utilities to suppress console windows on Windows.

When the application runs as a windowed (no-console) PyInstaller build,
every subprocess call (ffmpeg, ffprobe, ngrok, etc.) would normally pop up
a console window. These helpers prevent that by setting the appropriate
creation flags / startup info on Windows.
"""

from __future__ import annotations

import subprocess
import sys


def no_window_kwargs() -> dict:
    """Return kwargs to pass to subprocess.Popen/run/call/check_output
    that prevent a console window from appearing on Windows.

    On non-Windows platforms returns an empty dict (no-op).
    """
    if sys.platform != "win32":
        return {}

    kwargs: dict = {}
    # CREATE_NO_WINDOW prevents a console window for the child process.
    creationflags = 0
    creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    kwargs["creationflags"] = creationflags

    # Belt-and-suspenders: also hide via STARTUPINFO in case the child
    # tries to allocate a window.
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = startupinfo
    except Exception:
        pass

    return kwargs


# ── Windows Job Object: auto-kill child processes when parent exits ──

_job_handle = None


def ensure_job_object():
    """Create a Windows Job Object with KILL_ON_JOB_CLOSE.

    All processes assigned to this job will be terminated by the OS
    when the last handle to the job is closed (i.e. when our process exits,
    even on crash). This prevents orphaned ffmpeg.exe processes.

    Returns the job handle, or None on non-Windows / failure.
    """
    global _job_handle
    if _job_handle is not None:
        return _job_handle
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # CRITICAL: declare proper signatures so 64-bit HANDLEs are not
        # truncated to 32-bit ints (which would corrupt CloseHandle calls).
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
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
        # 9 = JobObjectExtendedLimitInformation
        kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(info), ctypes.sizeof(info)
        )
        _job_handle = job
        return _job_handle
    except Exception:
        return None


def assign_to_job(proc: subprocess.Popen) -> None:
    """Assign a subprocess to the kill-on-close Job Object.

    After this call, if our process exits (even via crash/kill),
    Windows will automatically terminate the child process.
    """
    if sys.platform != "win32":
        return
    job = ensure_job_object()
    if job is None:
        return
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # Proper signatures so the process HANDLE is a full 64-bit pointer.
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
    """Immediately terminate every process assigned to the Job Object.

    Used on graceful shutdown to kill all export subprocesses (visualizers
    and their ffmpeg children) at once. The KILL_ON_JOB_CLOSE limit also
    covers crash scenarios where this is never called.
    """
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
