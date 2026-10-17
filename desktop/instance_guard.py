"""Conservative recovery for a dead Qt single-instance lock on Windows."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path


def _process_started_at(pid: int) -> tuple[str, float | None]:
    """Return live/dead/unknown and the process creation time in Unix seconds."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ("dead" if ctypes.get_last_error() == 87 else "unknown", None)
    try:
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                      ctypes.byref(kernel_time), ctypes.byref(user_time)):
            return "unknown", None
        ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
        return "live", ticks / 10_000_000 - 11_644_473_600
    finally:
        kernel.CloseHandle(handle)


def inspect_lock(path: Path) -> tuple[bool, str, tuple | None]:
    """Only a dead PID or a provably reused PID permits recovery."""
    try:
        stat = path.stat()
        raw = path.read_bytes()
        pid = int(raw.splitlines()[0])
        if pid <= 0:
            return False, "invalid-pid", None
    except (OSError, ValueError, IndexError):
        return False, "unreadable-lock", None
    state, started_at = _process_started_at(pid)
    fingerprint = (stat.st_dev, stat.st_ino, stat.st_mtime_ns, raw)
    if state == "dead":
        return True, "owner-exited", fingerprint
    if state == "live" and started_at is not None and started_at > stat.st_mtime + 2:
        return True, "pid-reused", fingerprint
    return False, "owner-live-or-unknown", fingerprint


def remove_verified_lock(path: Path, fingerprint: tuple) -> bool:
    """Do not remove a lock that changed after inspection."""
    try:
        stat = path.stat()
        if (stat.st_dev, stat.st_ino, stat.st_mtime_ns, path.read_bytes()) != fingerprint:
            return False
        path.unlink()
        return True
    except OSError:
        return False
