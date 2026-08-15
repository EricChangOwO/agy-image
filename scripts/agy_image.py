#!/usr/bin/env python3
"""Generate an image via the agy (Antigravity) CLI in print mode.

This is a deterministic wrapper around `agy --print`. The agy CLI is an
agentic assistant whose image tool defaults to a 1024x1024 square canvas and
honours *aspect-ratio shorthand* ("4:5", "9:16") only inconsistently. The
reliable lever is to demand **exact pixel dimensions** and forbid the square
fallback — this script bakes that into the composed prompt, then verifies the
real output dimensions and optionally enforces the exact size with a local converter.

Prints a single JSON object to stdout:
{
  "out": "/abs/path.png",
  "requested": {"width": 1024, "height": 1536},
  "actual":    {"width": 1024, "height": 1536},
  "matched": true,
  "cropped": false,
  "format": "png",
  "agy_report": "…last line agy printed…",
  "source_artifact": "/home/user/.gemini/antigravity-cli/brain/…/image.jpg"
}

Auth / permissions:
  No API key. agy authenticates locally. This script adds
  `--dangerously-skip-permissions` because headless mode cannot prompt for the
  built-in image tool; set AGY_REQUIRE_PERMISSIONS=1 to rely on configured rules.

Notes:
  - agy 1.1.x normally writes generated images into its brain/artifact directory.
    The script discovers the new artifact and materializes it at --out.
  - Print mode buffers output: nothing is printed until agy finishes, so a
    generous --timeout (default 12m) is expected.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
# Image header parsing (no PIL dependency)                                     #
# --------------------------------------------------------------------------- #
def _png_size(data: bytes) -> Optional[Tuple[int, int]]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _jpeg_size(path: pathlib.Path) -> Optional[Tuple[int, int]]:
    with path.open("rb") as fh:
        if fh.read(2) != b"\xff\xd8":
            return None
        while True:
            marker = fh.read(2)
            if len(marker) < 2 or marker[0] != 0xFF:
                return None
            code = marker[1]
            # Standalone markers without a length payload.
            if code in (0xD8, 0xD9) or 0xD0 <= code <= 0xD7:
                continue
            length_bytes = fh.read(2)
            if len(length_bytes) < 2:
                return None
            length = struct.unpack(">H", length_bytes)[0]
            # SOF0..SOF15 (excluding DHT 0xC4, DAC 0xCC) carry dimensions.
            if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                payload = fh.read(5)
                if len(payload) < 5:
                    return None
                height, width = struct.unpack(">HH", payload[1:5])
                return width, height
            fh.seek(length - 2, os.SEEK_CUR)


def _webp_size(data: bytes) -> Optional[Tuple[int, int]]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    fmt = data[12:16]
    if fmt == b"VP8 ":
        w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return w, h
    if fmt == b"VP8L":
        b0, b1, b2, b3 = data[21], data[22], data[23], data[24]
        w = ((b1 & 0x3F) << 8 | b0) + 1
        h = ((b3 & 0x0F) << 10 | b2 << 2 | (b1 & 0xC0) >> 6) + 1
        return w, h
    if fmt == b"VP8X":
        w = (data[24] | data[25] << 8 | data[26] << 16) + 1
        h = (data[27] | data[28] << 8 | data[29] << 16) + 1
        return w, h
    return None


def detect_image(path: pathlib.Path) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    """Return (format, (width, height)) reading only the file header."""
    try:
        head = path.read_bytes()[:64]
    except OSError:
        return None, None
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", _png_size(head)
    if head[:2] == b"\xff\xd8":
        return "jpeg", _jpeg_size(path)
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp", _webp_size(head)
    return None, None


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def snapshot_agy_artifacts() -> Dict[str, int]:
    """Snapshot existing agy image artifacts so a later run can be isolated."""
    root = pathlib.Path.home() / ".gemini" / "antigravity-cli" / "brain"
    snapshot: Dict[str, int] = {}
    if not root.is_dir():
        return snapshot
    try:
        candidates = root.rglob("*")
        for path in candidates:
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                try:
                    snapshot[str(path.resolve())] = path.stat().st_mtime_ns
                except OSError:
                    continue
    except OSError:
        pass
    return snapshot


def find_generated_artifact(text: str, before: Dict[str, int]) -> Optional[pathlib.Path]:
    """Find the image created by the just-finished agy session.

    Prefer an explicit absolute path from agy's report. Fall back to a new or
    modified image under the Antigravity brain directory. The fallback is needed
    because print-mode output differs across agy releases.
    """
    candidates: List[pathlib.Path] = []
    path_pattern = re.compile(
        r"(?:file://)?(/[^\s\"'<>]+?\.(?:png|jpe?g|webp))(?=$|[\s\"'<>.,])",
        re.IGNORECASE,
    )
    for match in path_pattern.finditer(text.replace("\\/", "/")):
        path = pathlib.Path(match.group(1)).expanduser()
        if path.is_file() and detect_image(path)[1] is not None:
            try:
                key = str(path.resolve())
                mtime = path.stat().st_mtime_ns
            except OSError:
                continue
            if before.get(key) != mtime:
                candidates.append(path)
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime_ns)

    root = pathlib.Path.home() / ".gemini" / "antigravity-cli" / "brain"
    if not root.is_dir():
        return None
    try:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            try:
                key = str(path.resolve())
                mtime = path.stat().st_mtime_ns
            except OSError:
                continue
            if before.get(key) != mtime and detect_image(path)[1] is not None:
                candidates.append(path)
    except OSError:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime_ns) if candidates else None


# --------------------------------------------------------------------------- #
# Prompt composition                                                           #
# --------------------------------------------------------------------------- #
def compose_prompt(
    *,
    out_path: str,
    width: int,
    height: int,
    scene: str,
    refs: List[str],
    subject_anchor: Optional[str],
) -> str:
    lines: List[str] = []
    lines.append(
        "請直接使用你的內建圖片生成工具恰好一次，生成一張圖片。"
        "Use your native generate_image tool exactly once."
        f"\n外層程式的最終輸出目標是：{out_path}"
    )
    lines.append(
        "\n【重要｜輸出尺寸 / CRITICAL OUTPUT SIZE】\n"
        f"成品必須是精確的 {width} x {height} 像素（寬 {width}、高 {height}）。"
        f"The result MUST be exactly {width} x {height} pixels (width {width}, "
        f"height {height}). 不要輸出 1024x1024 方圖，也不要把方圖補邊或拉伸成這個尺寸。"
        " Do NOT output a 1024x1024 square, and do not pad or upscale a square "
        "to reach this size."
    )
    lines.append(
        "\n【執行紀律｜EXECUTION DISCIPLINE — 必讀】\n"
        "你（agy）就是圖片生成器本身。請『直接』用你內建的圖片生成工具 "
        "(your built-in generate_image tool) 產生這張圖。工具若將圖片存到自己的 "
        "artifact/brain 目錄，這是正常結果；外層程式會收集並轉存。不要只因 artifact "
        "路徑或格式和最終目標不同就再次生圖。"
        " 嚴禁執行任何 shell 指令、python 腳本、`agy_image.py`，也不要呼叫或載入 "
        "`agy-image` skill 或再開一個 agy/Antigravity session 來生圖。"
        " Do NOT run any shell command, python script, agy_image.py, or the "
        "agy-image skill, and do NOT spawn another agy session — generate the "
        "image yourself with your native image tool. Generate exactly one image, "
        "then report its artifact path and dimensions."
    )
    if refs:
        ref_block = "\n".join(f"- {r}" for r in refs)
        anchor = subject_anchor or "參考圖中的同一個人 / the same person as in the references"
        lines.append(
            "\n【角色參考圖 / CHARACTER REFERENCE】請先讀取以下參考圖，務必保持"
            "「同一個人」的臉部五官、髮型髮色、膚色與體型一致：\n"
            f"{ref_block}\n"
            "規則：參考圖擁有臉孔；prompt 只負責場景、服裝、光線、情緒與構圖。"
            "Reference owns the face; the prompt owns scene, wardrobe, lighting, "
            "mood, and composition. 不要重述五官、種族、膚色或既有髮型細節。"
            f"\nSubject anchor: {anchor}."
        )
    lines.append(f"\n【場景 / SCENE】\n{scene}")
    lines.append(
        "\n生成後請回報成品檔案的絕對路徑與實際輸出的像素尺寸 "
        "(report the absolute file path and the actual output pixel dimensions)."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Artifact materialization and size enforcement                                #
# --------------------------------------------------------------------------- #
def _desired_format(path: pathlib.Path) -> Optional[str]:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "png"
    if suffix in (".jpg", ".jpeg"):
        return "jpeg"
    if suffix == ".webp":
        return "webp"
    return None


def _ffmpeg_materialize(
    src: pathlib.Path,
    dst: pathlib.Path,
    target_w: int,
    target_h: int,
    crop: bool,
) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    _, size = detect_image(src)
    if not ffmpeg or not size:
        return False
    aw, ah = size
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(src)]
    if crop and (aw != target_w or ah != target_h):
        target_aspect = target_w / target_h
        if aw / ah > target_aspect:
            cw, ch = round(ah * target_aspect), ah
        else:
            cw, ch = aw, round(aw / target_aspect)
        x, y = (aw - cw) // 2, (ah - ch) // 2
        cmd += ["-vf", f"crop={cw}:{ch}:{x}:{y},scale={target_w}:{target_h}"]
    tmp = dst.with_name(f".{dst.stem}.agy-tmp{dst.suffix}")
    result = subprocess.run(cmd + [str(tmp)], capture_output=True, text=True)
    if result.returncode != 0 or not tmp.exists():
        if tmp.exists():
            tmp.unlink()
        return False
    tmp.replace(dst)
    return True


def _windows_path_from_wsl(path: pathlib.Path) -> Optional[str]:
    wslpath = shutil.which("wslpath")
    if not wslpath:
        return None
    result = subprocess.run(
        [wslpath, "-w", str(path)], capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _powershell_materialize(
    src: pathlib.Path,
    dst: pathlib.Path,
    target_w: int,
    target_h: int,
    crop: bool,
) -> bool:
    """Convert/crop through Windows System.Drawing when running under WSL."""
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        return False
    tmp = dst.with_name(f".{dst.stem}.agy-tmp{dst.suffix}")
    if tmp.exists():
        tmp.unlink()
    if os.name == "nt":
        src_arg, dst_arg = str(src), str(tmp)
    else:
        src_arg = _windows_path_from_wsl(src)
        dst_arg = _windows_path_from_wsl(tmp)
        if not src_arg or not dst_arg:
            return False
    fmt = _desired_format(dst)
    if fmt not in ("png", "jpeg"):
        return False

    def ps_quote(value: str) -> str:
        return value.replace("'", "''")

    save_format = "Png" if fmt == "png" else "Jpeg"
    crop_literal = "$true" if crop else "$false"
    script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$src = '{ps_quote(src_arg)}'
$dst = '{ps_quote(dst_arg)}'
$img = [System.Drawing.Image]::FromFile($src)
try {{
  if ({crop_literal} -and ($img.Width -ne {target_w} -or $img.Height -ne {target_h})) {{
    $targetAspect = {target_w}.0 / {target_h}.0
    $sourceAspect = $img.Width / [double]$img.Height
    if ($sourceAspect -gt $targetAspect) {{
      $cropH = $img.Height
      $cropW = [int][Math]::Round($img.Height * $targetAspect)
    }} else {{
      $cropW = $img.Width
      $cropH = [int][Math]::Round($img.Width / $targetAspect)
    }}
    $cropX = [int](($img.Width - $cropW) / 2)
    $cropY = [int](($img.Height - $cropH) / 2)
    $bmp = New-Object System.Drawing.Bitmap({target_w}, {target_h})
    try {{
      $g = [System.Drawing.Graphics]::FromImage($bmp)
      try {{
        $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g.DrawImage($img, (New-Object System.Drawing.Rectangle(0, 0, {target_w}, {target_h})), (New-Object System.Drawing.Rectangle($cropX, $cropY, $cropW, $cropH)), [System.Drawing.GraphicsUnit]::Pixel)
      }} finally {{ $g.Dispose() }}
      $bmp.Save($dst, [System.Drawing.Imaging.ImageFormat]::{save_format})
    }} finally {{ $bmp.Dispose() }}
  }} else {{
    $img.Save($dst, [System.Drawing.Imaging.ImageFormat]::{save_format})
  }}
}} finally {{ $img.Dispose() }}
"""
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not tmp.exists():
        if tmp.exists():
            tmp.unlink()
        return False
    tmp.replace(dst)
    return True


def materialize_artifact(
    src: pathlib.Path,
    dst: pathlib.Path,
    target_w: int,
    target_h: int,
    crop: bool,
) -> Tuple[bool, Optional[str]]:
    """Copy or convert an agy artifact to the requested destination."""
    fmt, size = detect_image(src)
    if not fmt or not size:
        return False, "generated artifact is not a supported image"
    desired = _desired_format(dst)
    if desired is None:
        return False, "output extension must be .png, .jpg, .jpeg, or .webp"
    resize_needed = size != (target_w, target_h)
    conversion_needed = fmt != desired
    dst.parent.mkdir(parents=True, exist_ok=True)

    if not conversion_needed and not (crop and resize_needed):
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        return True, None
    if _ffmpeg_materialize(src, dst, target_w, target_h, crop):
        return True, None
    if _powershell_materialize(src, dst, target_w, target_h, crop):
        return True, None
    return False, (
        "image conversion/size enforcement requires ffmpeg or Windows PowerShell "
        "System.Drawing (normally available under WSL on Windows)"
    )


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def build_add_dirs(out_path: pathlib.Path, refs: List[str],
                   refs_dir: Optional[str]) -> List[str]:
    candidates: List[pathlib.Path] = [out_path.parent]
    if refs_dir:
        candidates.append(pathlib.Path(refs_dir))
    for r in refs:
        candidates.append(pathlib.Path(r).parent)
    seen: List[str] = []
    for index, c in enumerate(candidates):
        try:
            resolved = str(c.resolve())
        except OSError:
            continue
        if (index == 0 or c.is_dir()) and resolved not in seen:
            seen.append(resolved)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an image with the agy (Antigravity) CLI at an exact pixel size."
    )
    parser.add_argument("--prompt", required=True,
                        help="Scene / subject description (the creative prompt).")
    parser.add_argument("--width", type=int, required=True, help="Exact output width in px.")
    parser.add_argument("--height", type=int, required=True, help="Exact output height in px.")
    parser.add_argument("--out", required=True,
                        help="Absolute output path, e.g. /home/user/agy_images/out.jpg")
    parser.add_argument("--ref", action="append", default=[],
                        help="Character reference image path (repeatable).")
    parser.add_argument("--refs-dir", default=None,
                        help="Directory of reference images to --add-dir into the workspace.")
    parser.add_argument("--subject-anchor", default=None,
                        help="Short subject anchor kept constant across a series, e.g. 'a young woman'.")
    parser.add_argument("--timeout", default="12m",
                        help="agy --print-timeout value (default 12m).")
    parser.add_argument("--crop", action="store_true",
                        help="If size drifts, center-crop and scale using ffmpeg or WSL PowerShell.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Allow replacing an existing output file.")
    parser.add_argument("--agy-bin", default="agy", help="agy binary (default 'agy').")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the composed prompt + command as JSON without running agy.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress logs on stderr.")
    args = parser.parse_args()

    def log(msg: str) -> None:
        if not args.quiet:
            print(msg, file=sys.stderr, flush=True)

    out_path = pathlib.Path(args.out).expanduser()
    if not out_path.is_absolute():
        out_path = out_path.resolve()
    if args.width <= 0 or args.height <= 0:
        print(json.dumps({"status": "failed", "error": "width and height must be positive"}))
        return 1
    if _desired_format(out_path) is None:
        print(json.dumps({
            "status": "failed",
            "error": "output extension must be .png, .jpg, .jpeg, or .webp",
            "out": str(out_path),
        }, ensure_ascii=False))
        return 1

    # Re-entrancy guard. This script drives `agy`, which is itself an Antigravity
    # *agent*: it can see the agy-image skill in ~/.openclaw/skills and "helpfully"
    # re-run this very script, spawning another agy → an unbounded
    # agy.real -> agy_image.py -> agy.real recursion that only ends when the caller
    # (e.g. a time-boxed autonomous cron) times out, producing no image. We mark depth in the
    # child env (below); if we're already inside an agy-image generation, refuse to
    # spawn another agy and tell the agent to use its native image tool instead.
    if os.environ.get("AGY_IMAGE_DEPTH"):
        print(json.dumps({
            "status": "failed",
            "error": ("agy-image re-entry blocked: already inside an agy-image "
                      "generation (AGY_IMAGE_DEPTH set). Do NOT run agy_image.py "
                      "here — use your built-in generate_image tool to create the "
                      f"image at {out_path} at exactly {args.width}x{args.height} px."),
            "out": str(out_path),
            "reentry": True,
        }, ensure_ascii=False))
        return 1

    refs = [str(pathlib.Path(r).expanduser()) for r in args.ref]
    missing = [r for r in refs if not pathlib.Path(r).exists()]
    if missing:
        print(json.dumps({"status": "failed", "error": "reference image(s) not found",
                          "missing": missing}, ensure_ascii=False))
        return 1

    prompt_text = compose_prompt(
        out_path=str(out_path), width=args.width, height=args.height,
        scene=args.prompt, refs=refs, subject_anchor=args.subject_anchor,
    )
    add_dirs = build_add_dirs(out_path, refs, args.refs_dir)

    cmd: List[str] = [args.agy_bin]
    if not os.environ.get("AGY_REQUIRE_PERMISSIONS"):
        cmd.append("--dangerously-skip-permissions")
    cmd += ["--disable-slash-commands", "--print-timeout", args.timeout]
    for d in add_dirs:
        cmd += ["--add-dir", d]
    cmd += ["--print", prompt_text]

    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "command": cmd[:-1] + ["<prompt>"],
            "add_dirs": add_dirs,
            "composed_prompt": prompt_text,
            "requested": {"width": args.width, "height": args.height},
            "out": str(out_path),
        }, ensure_ascii=False, indent=2))
        return 0

    if out_path.exists() and not args.overwrite:
        print(json.dumps({
            "status": "failed",
            "error": "output already exists; pass --overwrite only when replacement is intended",
            "out": str(out_path),
        }, ensure_ascii=False))
        return 1
    out_before_mtime = out_path.stat().st_mtime_ns if out_path.exists() else None
    out_path.parent.mkdir(parents=True, exist_ok=True)

    log(f"[agy-image] running agy (timeout {args.timeout}); add-dirs: {add_dirs}")
    log("[agy-image] print mode buffers output — this can take several minutes…")
    before_artifacts = snapshot_agy_artifacts()
    # Mark depth so a nested agy-image invocation (the inner agy re-running this
    # script) hits the re-entrancy guard above and fails fast instead of recursing.
    child_env = os.environ.copy()
    child_env["AGY_IMAGE_DEPTH"] = "1"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=child_env)
    except FileNotFoundError:
        print(json.dumps({
            "status": "failed",
            "error": f"agy binary not found: {args.agy_bin!r} — is it on PATH?",
            "out": str(out_path),
        }, ensure_ascii=False))
        return 1
    agy_stdout = (proc.stdout or "").strip()
    agy_stderr = (proc.stderr or "").strip()
    last_line = agy_stdout.splitlines()[-1] if agy_stdout else ""

    out_was_written = (
        out_path.exists()
        and (out_before_mtime is None or out_path.stat().st_mtime_ns != out_before_mtime)
    )
    artifact = out_path if out_was_written else find_generated_artifact(
        "\n".join((agy_stdout, agy_stderr)), before_artifacts
    )
    if artifact is None:
        print(json.dumps({
            "status": "failed",
            "error": "agy did not produce a discoverable image artifact",
            "exit_code": proc.returncode,
            "out": str(out_path),
            "agy_stdout_tail": agy_stdout[-800:],
            "agy_stderr_tail": agy_stderr[-800:],
        }, ensure_ascii=False))
        return 1

    source_format, source_size = detect_image(artifact)
    desired = _desired_format(out_path)
    needs_materialize = (
        artifact.resolve() != out_path.resolve()
        or source_format != desired
        or (args.crop and source_size != (args.width, args.height))
    )
    if needs_materialize:
        source_for_copy = artifact
        temp_dir: Optional[tempfile.TemporaryDirectory] = None
        if artifact.resolve() == out_path.resolve():
            temp_dir = tempfile.TemporaryDirectory(prefix="agy-image-")
            source_for_copy = pathlib.Path(temp_dir.name) / artifact.name
            shutil.copy2(artifact, source_for_copy)
        try:
            ok, materialize_error = materialize_artifact(
                source_for_copy, out_path, args.width, args.height, args.crop
            )
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()
        if not ok:
            print(json.dumps({
                "status": "failed",
                "error": materialize_error,
                "source_artifact": str(artifact),
                "out": str(out_path),
                "agy_stdout_tail": agy_stdout[-800:],
                "agy_stderr_tail": agy_stderr[-800:],
            }, ensure_ascii=False))
            return 1

    fmt, size = detect_image(out_path)
    cropped = bool(
        args.crop and source_size is not None
        and source_size != (args.width, args.height)
        and size == (args.width, args.height)
    )
    if size is None:
        # File exists but header unparsed; report what we can.
        result: Dict[str, Any] = {
            "status": "completed",
            "out": str(out_path),
            "requested": {"width": args.width, "height": args.height},
            "actual": None,
            "matched": False,
            "cropped": False,
            "format": fmt,
            "agy_report": last_line,
            "source_artifact": str(artifact),
            "warning": "could not parse output dimensions from header",
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    aw, ah = size
    matched = (aw == args.width and ah == args.height)
    result = {
        "status": "completed",
        "out": str(out_path),
        "requested": {"width": args.width, "height": args.height},
        "actual": {"width": aw, "height": ah},
        "matched": matched,
        "cropped": cropped,
        "format": fmt,
        "agy_report": last_line,
        "source_artifact": str(artifact),
        "exit_code": proc.returncode,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
