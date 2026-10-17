"""Reliable Windows launcher for the Yayan desktop pet.

This launcher only recovers processes whose command line or executable path
proves that they belong to this checkout.  It never deletes the Qt lock file.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
MAIN = PROJECT_DIR / "desktop" / "main.pyw"
RUNTIME_DIR = PROJECT_DIR / "output" / "runtime"
STARTUP_LOG = RUNTIME_DIR / "desktop-startup.log"
LAUNCH_LOG = RUNTIME_DIR / "start-command.log"
CREATE_NEW_CONSOLE = 0x00000010


def log(message: str, **details: object) -> None:
    record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": message, **details}
    with LAUNCH_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def fail(message: str) -> int:
    print(f"YAYAN_START_FAILED: {message}")
    log("launcher-failed", error=message)
    return 1


def project_processes() -> list[dict[str, object]]:
    """Return only processes provably owned by this project checkout."""
    script = r'''
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$root = [IO.Path]::GetFullPath($env:YAYAN_ROOT).TrimEnd('\')
$main = ($root + '\desktop\main.pyw').ToLowerInvariant()
$godot = ($root + '\output\godot\YayanPet.exe').ToLowerInvariant()
$rows = @(
  Get-CimInstance Win32_Process | Where-Object {
    ($_.CommandLine -and $_.CommandLine.ToLowerInvariant().Contains($main)) -or
    ($_.ExecutablePath -and $_.ExecutablePath.ToLowerInvariant() -eq $godot)
  } | Select-Object ProcessId,Name,ExecutablePath,CommandLine
)
if ($rows.Count -eq 0) { '[]' } else { $rows | ConvertTo-Json -Compress }
'''
    env = os.environ.copy()
    env["YAYAN_ROOT"] = str(PROJECT_DIR)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "process inspection failed")
    raw = result.stdout.strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        return [data]
    return list(data)


def recover_old_processes() -> list[int]:
    """Gracefully request quit, then force-stop verified project processes."""
    try:
        subprocess.run(
            [str(PYTHON), str(MAIN), "--quit"],
            cwd=PROJECT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass

    time.sleep(0.4)
    processes = project_processes()
    killed: list[int] = []
    for row in processes:
        pid = int(row["ProcessId"])
        name = str(row.get("Name") or "")
        executable = str(row.get("ExecutablePath") or "")
        command_line = str(row.get("CommandLine") or "")
        print(f"recovery-candidate pid={pid} name={name} exe={executable}")
        log(
            "recovery-candidate",
            pid=pid,
            name=name,
            executable=executable,
            command_line=command_line,
        )
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, check=False)
        killed.append(pid)

    if killed:
        time.sleep(0.6)
        remaining = project_processes()
        if remaining:
            raise RuntimeError(f"project processes did not exit: {[p['ProcessId'] for p in remaining]}")
    return killed


def read_new_events(start_offset: int) -> tuple[int, list[dict[str, object]]]:
    if not STARTUP_LOG.exists():
        return start_offset, []
    with STARTUP_LOG.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(start_offset)
        events: list[dict[str, object]] = []
        for line in stream:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return stream.tell(), events


def reveal_window() -> int | None:
    """Show the project's Godot window once it exists; return its HWND."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.SetProcessDPIAware()
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    found: list[tuple[int, int]] = []

    def callback(hwnd: int, _param: int) -> bool:
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, len(title))
        if title.value != "YayanPet":
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = kernel32.OpenProcess(0x1000, False, pid.value)
        if not process:
            return True
        try:
            path = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(len(path))
            kernel32.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(size))
            expected = str(PROJECT_DIR / "output" / "godot" / "YayanPet.exe").lower()
            if path.value.lower() == expected:
                found.append((int(hwnd), int(pid.value)))
        finally:
            kernel32.CloseHandle(process)
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    if len(found) != 1:
        return None
    hwnd, _pid = found[0]
    user32.ShowWindow(hwnd, 1)
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
    user32.SetForegroundWindow(hwnd)
    return hwnd


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    log("launcher-start", project=str(PROJECT_DIR), python=str(PYTHON), main=str(MAIN))
    if os.name != "nt":
        return fail("this launcher requires Windows")
    if not PYTHON.is_file():
        return fail(f"missing interpreter: {PYTHON}")
    if not MAIN.is_file():
        return fail(f"missing main program: {MAIN}")

    try:
        subprocess.run(
            [str(PYTHON), "-c", "import PyQt5, openai, keyring"],
            cwd=PROJECT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        return fail(f"Python environment check failed: {error}")

    try:
        killed = recover_old_processes()
    except (OSError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        return fail(f"safe recovery failed: {error}")
    if killed:
        print(f"recovered-project-pids={killed}")
        log("recovery-complete", pids=killed)

    start_offset = STARTUP_LOG.stat().st_size if STARTUP_LOG.exists() else 0
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        process = subprocess.Popen(
            [str(PYTHON), str(MAIN)],
            cwd=PROJECT_DIR,
            env=env,
            creationflags=CREATE_NEW_CONSOLE,
        )
    except OSError as error:
        return fail(f"cannot launch main program: {error}")
    print(f"python-pid={process.pid}")
    log("python-launch", pid=process.pid)

    offset = start_offset
    events: list[dict[str, object]] = []
    deadline = time.monotonic() + 15
    window_handle: int | None = None
    while time.monotonic() < deadline:
        offset, new_events = read_new_events(offset)
        events.extend(new_events)
        if window_handle is None:
            try:
                window_handle = reveal_window()
            except OSError:
                window_handle = None
        ipc_ready = any(
            event.get("event") == "ipc-listen" and event.get("listening")
            for event in events
        )
        godot_mode = any(
            event.get("event") == "pet-renderer" and event.get("active") == "godot"
            for event in events
        )
        godot_ready = any(event.get("event") == "godot-launch" for event in events)
        if ipc_ready and (not godot_mode or (godot_ready and window_handle is not None)):
            godot = next((event for event in events if event.get("event") == "godot-launch"), None)
            print("YAYAN_START_OK")
            print(f"godot-pid={godot.get('pid') if godot else 'unknown'}")
            print(f"window-hwnd={window_handle if window_handle is not None else 'not-found'}")
            log("launcher-ready", python_pid=process.pid, window_handle=window_handle)
            return 0
        if process.poll() is not None:
            tail = " | ".join(json.dumps(event, ensure_ascii=False) for event in events[-3:])
            return fail(f"main exited with code {process.returncode}; {tail}")
        time.sleep(0.25)

    tail = " | ".join(json.dumps(event, ensure_ascii=False) for event in events[-5:])
    return fail(f"startup timed out; recent events: {tail}")


if __name__ == "__main__":
    raise SystemExit(main())
