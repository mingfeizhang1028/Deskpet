"""Yayan 桌面宠物的一键引导脚本。

职责（只做"准备"，不做具体启动）：
- 确保虚拟环境存在：首次运行自动创建 .venv 并安装 requirements.txt；
- 确保动画渲染包存在（output/godot/YayanPet.exe + YayanPet.pck），
  缺失时从 GitHub Release 自动下载；下载失败不中断，
  主程序会自动回退到 PyQt 渲染（见 desktop/main.pyw）；
- 准备完成后交给可靠的启动器 scripts/start_yayan.py。

用法：由 Start-Yayan.cmd 用系统 Python 调用（此时 venv 可能还不存在）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
RENDERER_DIR = PROJECT_DIR / "output" / "godot"
RENDERER_EXE = RENDERER_DIR / "YayanPet.exe"
RENDERER_PCK = RENDERER_DIR / "YayanPet.pck"
RUNTIME_DIR = PROJECT_DIR / "output" / "runtime"
BOOTSTRAP_LOG = RUNTIME_DIR / "bootstrap.log"
START_SCRIPT = PROJECT_DIR / "scripts" / "start_yayan.py"

# 预编译的动画渲染包（免装 Godot）。随仓库 Release 一起发布；
# 可用环境变量 YAYAN_RENDERER_URL 覆盖，便于本地测试或镜像。
DEFAULT_RENDERER_URL = (
    "https://github.com/mingfeizhang1028/Deskpet/releases/latest/download/yayan-renderer-win64.zip"
)


def log(message: str, **details: object) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": message, **details}
    with BOOTSTRAP_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def ensure_venv() -> bool:
    """确保 .venv 存在且已安装依赖。已存在直接成功；创建失败返回 False。"""
    if VENV_PYTHON.is_file():
        return True
    print("[Yayan] First run: creating virtual environment and installing dependencies ...")
    log("bootstrap-venv", action="create")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[Yayan] Failed to set up the Python environment: {error}")
        log("bootstrap-venv", action="fail", error=str(error))
        return False
    log("bootstrap-venv", action="done")
    return True


def renderer_ready() -> bool:
    return RENDERER_EXE.is_file() and RENDERER_PCK.is_file()


def _safe_extract(bundle: zipfile.ZipFile, target: Path) -> None:
    """解压到 target，拒绝绝对路径与 .. 逃逸，避免恶意压缩包写到目录外。"""
    for member in bundle.infolist():
        name = member.filename.replace("\\", "/")
        parts = Path(name).parts
        if name.startswith("/") or ".." in parts or (len(parts) > 1 and parts[1] == ".."):
            raise zipfile.BadZipFile(f"unsafe path in archive: {member.filename}")
    bundle.extractall(target)


def ensure_renderer() -> bool:
    """确保动画渲染包就位。缺失时从 Release 下载；失败返回 False（不阻断启动）。"""
    if renderer_ready():
        return True
    if os.environ.get("YAYAN_SKIP_RENDERER_DOWNLOAD") == "1":
        print("[Yayan] Renderer download skipped (YAYAN_SKIP_RENDERER_DOWNLOAD=1).")
        log("bootstrap-renderer", action="skip")
        return False
    url = os.environ.get("YAYAN_RENDERER_URL", DEFAULT_RENDERER_URL)
    print("[Yayan] First run: downloading the animation renderer package (one-time) ...")
    log("bootstrap-renderer", action="start", url=url)
    scratch = PROJECT_DIR / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    archive = scratch / "yayan-renderer-win64.zip"
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            with archive.open("wb") as out:
                downloaded = 0
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        percent = downloaded * 100 // total
                        print(f"\r[Yayan] Downloading renderer ... {percent}%", end="", flush=True)
        print()
        RENDERER_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            _safe_extract(bundle, RENDERER_DIR)
        archive.unlink(missing_ok=True)
    except (OSError, urllib.error.URLError, zipfile.BadZipFile) as error:
        print(f"[Yayan] Renderer download failed: {error}")
        print("[Yayan] Continuing without it; the pet falls back to the PyQt renderer.")
        log("bootstrap-renderer", action="fail", error=str(error))
        return False
    if not renderer_ready():
        print("[Yayan] Renderer package incomplete after download; falling back to PyQt.")
        log("bootstrap-renderer", action="incomplete")
        return False
    log("bootstrap-renderer", action="done")
    return True


def main() -> int:
    if os.name != "nt":
        print("[Yayan] This launcher requires Windows.")
        return 1
    if not ensure_venv():
        return 1
    ensure_renderer()  # 失败不阻断：主程序会自动回退到 PyQt 渲染
    if not START_SCRIPT.is_file():
        print(f"[Yayan] Missing launcher: {START_SCRIPT}")
        return 1
    result = subprocess.run([str(VENV_PYTHON), str(START_SCRIPT)])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
