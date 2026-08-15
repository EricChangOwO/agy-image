#!/usr/bin/env python3
"""Detect the agy execution environment and normalize paths for that runtime."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple


WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def runtime_kind() -> str:
    if os.name == "nt":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        release = platform.release().lower()
        if (
            os.environ.get("WSL_DISTRO_NAME")
            or "microsoft" in release
            or pathlib.Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists()
        ):
            return "wsl"
        return "linux"
    return sys.platform


def decode_wsl_output(data: bytes) -> str:
    if not data:
        return ""
    if b"\x00" in data:
        return data.decode("utf-16-le", errors="replace").lstrip("\ufeff")
    return data.decode(errors="replace").lstrip("\ufeff")


def list_wsl_distros(wsl: str) -> List[str]:
    proc = subprocess.run([wsl, "--list", "--quiet"], capture_output=True)
    if proc.returncode != 0:
        return []
    seen: List[str] = []
    for line in decode_wsl_output(proc.stdout).replace("\x00", "").splitlines():
        name = line.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def probe_wsl_agy(wsl: str, distro: str) -> Tuple[Optional[str], Optional[str]]:
    proc = subprocess.run(
        [
            wsl,
            "-d",
            distro,
            "--",
            "bash",
            "-lc",
            "command -v agy && agy --version 2>/dev/null | head -n 1",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        return None, None
    lines = [
        line.strip()
        for line in decode_wsl_output(proc.stdout).replace("\x00", "").splitlines()
        if line.strip()
    ]
    return (lines[0], lines[1] if len(lines) > 1 else None) if lines else (None, None)


def probe_login_agy() -> Tuple[Optional[str], Optional[str]]:
    bash = shutil.which("bash")
    if not bash:
        return None, None
    proc = subprocess.run(
        [bash, "-lc", "command -v agy && agy --version 2>/dev/null | head -n 1"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None, None
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return (lines[0], lines[1] if len(lines) > 1 else None) if lines else (None, None)


def translate_to_wsl(path: str, wsl: str, distro: str) -> Tuple[Optional[str], Optional[str]]:
    if path.startswith("/"):
        return path, None
    if not WINDOWS_PATH.match(path):
        return None, "path is neither an absolute Windows path nor an absolute POSIX path"
    normalized = path.replace("\\", "/")
    proc = subprocess.run(
        [wsl, "-d", distro, "--", "wslpath", "-u", normalized],
        capture_output=True,
    )
    if proc.returncode != 0:
        error = decode_wsl_output(proc.stderr).replace("\x00", "").strip()
        return None, error or "wslpath conversion failed"
    translated = decode_wsl_output(proc.stdout).replace("\x00", "").strip()
    return (translated or None), (None if translated else "wslpath returned an empty path")


def normalize_current_path(path: str, kind: str) -> Tuple[Optional[str], Optional[str]]:
    if kind == "windows":
        if path.startswith("/") and not WINDOWS_PATH.match(path):
            return None, "POSIX/WSL path cannot be passed to Windows Python"
        return str(pathlib.Path(path).expanduser().resolve()), None
    if WINDOWS_PATH.match(path):
        wslpath = shutil.which("wslpath") if kind == "wsl" else None
        if not wslpath:
            return None, f"Windows path cannot be used directly in {kind}"
        proc = subprocess.run(
            [wslpath, "-u", path.replace("\\", "/")], capture_output=True, text=True
        )
        if proc.returncode != 0:
            return None, (proc.stderr or "wslpath conversion failed").strip()
        return proc.stdout.strip(), None
    if not path.startswith("/"):
        return None, "use an absolute path before invoking the generation wrapper"
    return str(pathlib.Path(path).expanduser().resolve()), None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect where agy can run and translate paths for that runtime."
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Absolute skill/output/reference path to normalize (repeatable).",
    )
    args = parser.parse_args()

    kind = runtime_kind()
    current_agy = shutil.which("agy")
    current_agy_version: Optional[str] = None
    current_agy_source = "process-path" if current_agy else None
    if not current_agy and kind in ("wsl", "linux", "macos"):
        current_agy, current_agy_version = probe_login_agy()
        if current_agy:
            current_agy_source = "login-shell-path"
    result: Dict[str, Any] = {
        "runtime": {
            "kind": kind,
            "os_name": os.name,
            "platform": sys.platform,
            "python": sys.executable,
            "python_version": platform.python_version(),
            "cwd": str(pathlib.Path.cwd()),
            "path_style": "windows" if kind == "windows" else "posix",
        },
        "agy": {
            "current_runtime_path": current_agy,
            "version": current_agy_version,
            "discovered_via": current_agy_source,
        },
        "wsl": None,
    }

    generation: Dict[str, Any]
    wsl_exe: Optional[str] = None
    selected_distro: Optional[str] = None
    if current_agy:
        generation = {
            "mode": "current-runtime",
            "runtime": kind,
            "path_style": "windows" if kind == "windows" else "posix",
            "agy_path": current_agy,
            "agy_version": current_agy_version,
            "launcher": [sys.executable],
        }
        status = "ready"
    elif kind == "windows" and (wsl_exe := shutil.which("wsl.exe")):
        distros = list_wsl_distros(wsl_exe)
        probes: List[Dict[str, Optional[str]]] = []
        selected_path: Optional[str] = None
        selected_version: Optional[str] = None
        for distro in distros:
            agy_path, version = probe_wsl_agy(wsl_exe, distro)
            probes.append({"distro": distro, "agy_path": agy_path, "version": version})
            if agy_path:
                selected_distro = distro
                selected_path = agy_path
                selected_version = version
                break
        result["wsl"] = {
            "available": True,
            "distros": distros,
            "probes": probes,
        }
        if selected_distro and selected_path:
            generation = {
                "mode": "wsl",
                "runtime": "wsl",
                "distro": selected_distro,
                "path_style": "posix",
                "agy_path": selected_path,
                "agy_version": selected_version,
                "launcher": ["wsl.exe", "-d", selected_distro, "--", "python3"],
            }
            status = "ready"
        else:
            generation = {
                "mode": "unavailable",
                "reason": "agy was not found in Windows or any detected WSL distro",
            }
            status = "missing-agy"
    else:
        if kind == "windows":
            result["wsl"] = {"available": False, "distros": [], "probes": []}
        generation = {
            "mode": "unavailable",
            "reason": f"agy was not found in the {kind} runtime",
        }
        status = "missing-agy"

    translated_paths: List[Dict[str, Optional[str]]] = []
    for raw_path in args.path:
        if generation.get("mode") == "wsl" and wsl_exe and selected_distro:
            translated, error = translate_to_wsl(raw_path, wsl_exe, selected_distro)
        elif generation.get("mode") == "current-runtime":
            translated, error = normalize_current_path(raw_path, kind)
        else:
            translated, error = None, "no usable agy runtime was detected"
        translated_paths.append(
            {"input": raw_path, "generation_path": translated, "error": error}
        )

    if status == "ready" and any(item["error"] for item in translated_paths):
        status = "invalid-paths"

    result.update(
        {
            "status": status,
            "generation": generation,
            "translated_paths": translated_paths,
            "rules": [
                "Run agy_image.py with the Python runtime selected in generation.launcher.",
                "Pass generation.agy_path through agy_image.py --agy-bin; do not rely on shell profile PATH.",
                "Pass only generation.path_style paths to --out, --ref, and --refs-dir.",
                "Do not use pathlib from one OS to reinterpret another OS path syntax.",
                "Keep storyboard paths relative to the beatmap; convert only filesystem paths.",
            ],
        }
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
