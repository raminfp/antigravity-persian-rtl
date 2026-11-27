#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Persian RTL & Vazirmatn Smart Patcher + Launcher (V2 Studio Edition)
Supports both Antigravity Desktop (2.0 ASAR) and Antigravity IDE (VS Code-based).
Zero external dependencies (pure Python 3 standard library).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import stat
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MARKER_ID = "AGY_PERSIAN_RTL_V1"
JS_START = f"/* {MARKER_ID}_START */"
JS_END = f"/* {MARKER_ID}_END */"
CSS_START = f"/* {MARKER_ID}_START */"
CSS_END = f"/* {MARKER_ID}_END */"
HTML_START = f"<!-- {MARKER_ID}_START -->"
HTML_END = f"<!-- {MARKER_ID}_END -->"

ASAR_BLOCK_SIZE = 4 * 1024 * 1024
FUSE_SENTINEL = b"dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX"

SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR / "assets"
DEFAULT_STATE_DIR = SCRIPT_DIR / "state"


def _extract_exec_target_from_wrapper(wrapper_path: Path) -> Optional[Path]:
    """If wrapper_path is a POSIX shell script calling `exec /path/to/binary ...`, return that binary path."""
    try:
        head = wrapper_path.read_bytes()[:4096]
        if not head.startswith(b"#!"):
            return None
        text = head.decode("utf-8", errors="ignore")
    except OSError:
        return None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("exec "):
            try:
                tokens = shlex.split(stripped[5:])
            except ValueError:
                tokens = stripped[5:].split()
            for tok in tokens:
                if tok.startswith("-"):
                    continue
                p = Path(os.path.expandvars(os.path.expanduser(tok)))
                if p.is_file():
                    return p.resolve()
    return None


def _candidate_dir_from_which(cmd_name: str, marker_rel: str) -> Optional[Path]:
    found = shutil.which(cmd_name)
    if not found:
        return None
    p = Path(found)
    resolved = p.resolve()
    if (resolved.parent / marker_rel).exists():
        return resolved.parent
    target = _extract_exec_target_from_wrapper(p)
    if target and (target.parent / marker_rel).exists():
        return target.parent
    return None


def default_desktop_dir() -> Path:
    env_dir = os.environ.get("ANTIGRAVITY_DESKTOP_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        return Path(local) / "Programs" / "antigravity"
    for cmd in ("antigravity", "Antigravity"):
        found = _candidate_dir_from_which(cmd, "resources/app.asar")
        if found:
            return found
    home = Path.home()
    for c in (
        home / "Downloads" / "Antigravity" / "Antigravity-x64",
        home / ".local" / "share" / "antigravity",
        home / ".local" / "share" / "Antigravity",
        home / "Applications" / "Antigravity",
        home / "Applications" / "Antigravity-x64",
        Path("/opt/Antigravity"),
        Path("/opt/antigravity"),
        Path("/usr/share/antigravity"),
        Path("/usr/lib/antigravity"),
    ):
        if (c / "resources" / "app.asar").exists():
            return c
    return Path("/opt/antigravity")


def default_ide_dir() -> Path:
    env_dir = os.environ.get("ANTIGRAVITY_IDE_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        return Path(local) / "Programs" / "Antigravity IDE"
    for cmd in ("antigravity-ide", "Antigravity-IDE"):
        found = _candidate_dir_from_which(cmd, "resources/app")
        if found:
            return found
    home = Path.home()
    for c in (
        home / ".local" / "share" / "antigravity-ide",
        home / ".local" / "share" / "Antigravity IDE",
        home / "Applications" / "Antigravity-IDE",
        Path("/opt/antigravity-ide"),
        Path("/opt/Antigravity IDE"),
        Path("/usr/share/antigravity-ide"),
        Path("/usr/lib/antigravity-ide"),
    ):
        if (c / "resources" / "app").exists():
            return c
    return Path("/opt/antigravity-ide")


def find_desktop_executable(desktop_dir: Path) -> Optional[Path]:
    names = ("Antigravity.exe",) if sys.platform == "win32" else ("antigravity", "Antigravity", "Antigravity.exe")
    for name in names:
        p = desktop_dir / name
        if p.is_file():
            return p
    return None


def find_ide_executable(ide_dir: Path) -> Optional[Path]:
    names = ("Antigravity IDE.exe",) if sys.platform == "win32" else ("antigravity-ide", "antigravity", "Antigravity IDE", "Antigravity IDE.exe")
    for name in names:
        p = ide_dir / name
        if p.is_file():
            return p
    return None


def find_wrapper_for_dir(cmd_name: str, app_dir: Path) -> Optional[Path]:
    found = shutil.which(cmd_name)
    if not found:
        return None
    p = Path(found)
    target = _extract_exec_target_from_wrapper(p)
    if target and target.parent.resolve() == app_dir.resolve():
        return p
    return None


def find_linux_app_icon(app_dir: Path, is_ide: bool = False) -> str:
    home = Path.home()
    for c in (
        home / ".local" / "share" / "icons" / ("antigravity-ide.png" if is_ide else "antigravity.png"),
        home / ".local" / "share" / "icons" / "antigravity.png",
        app_dir / "resources" / "app" / "resources" / "linux" / "code.png",
        Path("/usr/share/pixmaps/antigravity.png"),
        Path("/usr/share/icons/hicolor/256x256/apps/antigravity.png"),
    ):
        if c.is_file():
            return str(c)
    return "antigravity"


def load_assets() -> Tuple[str, str, str]:
    css_path = ASSETS_DIR / "agy-rtl.css"
    js_path = ASSETS_DIR / "agy-rtl.js"
    css = css_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")
    payload_hash = hashlib.sha256((css + "\n" + js).encode("utf-8")).hexdigest()[:16]
    return css, js, payload_hash


def strip_marked_block(content: str, start_marker: str, end_marker: str) -> str:
    while True:
        s = content.find(start_marker)
        if s == -1:
            break
        e = content.find(end_marker, s)
        if e == -1:
            content = content[:s]
            break
        e_end = e + len(end_marker)
        while e_end < len(content) and content[e_end] in ("\r", "\n"):
            e_end += 1
        while s > 0 and content[s - 1] in ("\r", "\n"):
            s -= 1
        content = content[:s] + ("\n" if s > 0 and e_end < len(content) else "") + content[e_end:]
    return content


def build_main_js_snippet(css_text: str) -> str:
    css_json = json.dumps(css_text, ensure_ascii=False)
    return (
        f"\n{JS_START}\n"
        ";(function () {\n"
        "  try {\n"
        "    const electron = require('electron');\n"
        "    const app = electron && electron.app;\n"
        "    if (!app || typeof app.on !== 'function') return;\n"
        f"    const RTL_CSS = {css_json};\n"
        "    app.on('web-contents-created', (_event, contents) => {\n"
        "      try {\n"
        "        if (!contents || (typeof contents.getType === 'function' && contents.getType() === 'webview')) return;\n"
        "        contents.on('dom-ready', () => {\n"
        "          try {\n"
        "            if (typeof contents.isDestroyed === 'function' && contents.isDestroyed()) return;\n"
        "            const u = (typeof contents.getURL === 'function' && contents.getURL()) || '';\n"
        "            if (\n"
        "              u.startsWith('https://127.0.0.1:') ||\n"
        "              u.startsWith('http://127.0.0.1:') ||\n"
        "              u.startsWith('https://localhost:') ||\n"
        "              u.startsWith('http://localhost:') ||\n"
        "              u.startsWith('app:') ||\n"
        "              u.startsWith('file:')\n"
        "            ) {\n"
        "              Promise.resolve(contents.insertCSS(RTL_CSS, { cssOrigin: 'user' })).catch(() => {});\n"
        "            }\n"
        "          } catch (_) {}\n"
        "        });\n"
        "      } catch (_) {}\n"
        "    });\n"
        "  } catch (_) {}\n"
        "})();\n"
        f"{JS_END}\n"
    )


def build_preload_js_snippet(css_text: str, js_text: str) -> str:
    css_json = json.dumps(css_text, ensure_ascii=False)
    return (
        f"\n{JS_START}\n"
        ";(function () {\n"
        "  try {\n"
        f"    const RTL_CSS = {css_json};\n"
        "    function injectFallbackStyle() {\n"
        "      try {\n"
        "        if (typeof document === 'undefined' || !document.head) return;\n"
        "        if (document.getElementById('agy-persian-rtl-style')) return;\n"
        "        const proto = (typeof location !== 'undefined' && location.protocol) || '';\n"
        "        const host = (typeof location !== 'undefined' && location.hostname) || '';\n"
        "        if (host !== '127.0.0.1' && host !== 'localhost' && proto !== 'app:' && proto !== 'file:') return;\n"
        "        const style = document.createElement('style');\n"
        "        style.id = 'agy-persian-rtl-style';\n"
        "        style.textContent = RTL_CSS;\n"
        "        document.head.appendChild(style);\n"
        "      } catch (_) {}\n"
        "    }\n"
        "    if (typeof document !== 'undefined') {\n"
        "      if (document.readyState === 'loading') {\n"
        "        document.addEventListener('DOMContentLoaded', injectFallbackStyle, { once: true });\n"
        "      } else {\n"
        "        injectFallbackStyle();\n"
        "      }\n"
        "    }\n"
        "  } catch (_) {}\n"
        "})();\n"
        f"{js_text}\n"
        f"{JS_END}\n"
    )


# ---------------------------------------------------------------------------
# Electron Fuse Check (Read-Only Safety Guard)
# ---------------------------------------------------------------------------

def is_asar_integrity_fuse_enabled(exe_path: Optional[Path]) -> bool:
    if not exe_path or not exe_path.exists():
        return False
    try:
        data = exe_path.read_bytes()
        idx = data.find(FUSE_SENTINEL)
        if idx == -1:
            return False
        length = data[idx + 33]
        if length <= 4:
            return False
        fuse_char = chr(data[idx + 34 + 4])
        return fuse_char == "1"
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Pure-Python ASAR Reader / Rebuilder
# ---------------------------------------------------------------------------

def compute_integrity(data: bytes) -> Dict[str, Any]:
    full_hash = hashlib.sha256(data).hexdigest()
    blocks = [
        hashlib.sha256(data[i : i + ASAR_BLOCK_SIZE]).hexdigest()
        for i in range(0, len(data), ASAR_BLOCK_SIZE)
    ]
    if not blocks:
        blocks = [hashlib.sha256(b"").hexdigest()]
    return {
        "algorithm": "SHA256",
        "hash": full_hash,
        "blockSize": ASAR_BLOCK_SIZE,
        "blocks": blocks,
    }


def parse_asar_header(asar_path: Path) -> Tuple[Dict[str, Any], int]:
    with asar_path.open("rb") as f:
        prefix = f.read(16)
        if len(prefix) < 16:
            raise ValueError(f"Invalid ASAR archive: {asar_path}")
        u0, header_size, _u2, json_size = struct.unpack("<IIII", prefix)
        if u0 != 4:
            raise ValueError(f"Unexpected ASAR pickle header u0={u0} in {asar_path}")
        json_bytes = f.read(json_size)
    header = json.loads(json_bytes.decode("utf-8"))
    payload_start = 8 + header_size
    return header, payload_start


def get_asar_node(header: Dict[str, Any], rel_path: str) -> Optional[Dict[str, Any]]:
    node: Dict[str, Any] = header
    for part in rel_path.strip("/").split("/"):
        files = node.get("files")
        if not isinstance(files, dict) or part not in files:
            return None
        node = files[part]
    return node


def read_asar_text_file(asar_path: Path, header: Dict[str, Any], payload_start: int, rel_path: str) -> Optional[str]:
    node = get_asar_node(header, rel_path)
    if not node or "files" in node or node.get("unpacked"):
        return None
    offset = payload_start + int(node["offset"])
    size = int(node["size"])
    with asar_path.open("rb") as f:
        f.seek(offset)
        return f.read(size).decode("utf-8")


def find_asar_preload_paths(header: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []

    def walk(node: Dict[str, Any], prefix: str = "") -> None:
        for name, child in node.get("files", {}).items():
            p = f"{prefix}/{name}" if prefix else name
            if "files" in child:
                if name != "node_modules":
                    walk(child, p)
            elif not child.get("unpacked"):
                if name == "preload.js":
                    candidates.append(p)

    walk(header)
    return candidates


def rebuild_asar_with_replacements(asar_path: Path, replacements: Dict[str, bytes]) -> None:
    raw = asar_path.read_bytes()
    u0, header_size, _u2, json_size = struct.unpack("<IIII", raw[:16])
    if u0 != 4:
        raise ValueError(f"Invalid ASAR header in {asar_path}")
    header = json.loads(raw[16 : 16 + json_size].decode("utf-8"))
    orig_payload_start = 8 + header_size

    payload_chunks: List[bytes] = []
    current_offset = 0

    def walk_update(node: Dict[str, Any], prefix: str = "") -> None:
        nonlocal current_offset
        for name, child in node.get("files", {}).items():
            p = f"{prefix}/{name}" if prefix else name
            if "files" in child:
                walk_update(child, p)
            elif child.get("unpacked"):
                continue
            else:
                if p in replacements:
                    chunk = replacements[p]
                    child["size"] = len(chunk)
                    if "integrity" in child:
                        child["integrity"] = compute_integrity(chunk)
                else:
                    old_off = orig_payload_start + int(child["offset"])
                    old_sz = int(child["size"])
                    chunk = raw[old_off : old_off + old_sz]
                child["offset"] = str(current_offset)
                payload_chunks.append(chunk)
                current_offset += len(chunk)

    walk_update(header)

    new_json_bytes = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    new_json_size = len(new_json_bytes)
    padded_json_len = (new_json_size + 3) & ~3
    padding = b"\x00" * (padded_json_len - new_json_size)
    new_u2 = 4 + padded_json_len
    new_header_size = 8 + padded_json_len
    new_prefix = struct.pack("<IIII", 4, new_header_size, new_u2, new_json_size) + new_json_bytes + padding

    tmp_path = asar_path.with_name(asar_path.name + ".rtl-tmp")
    try:
        with tmp_path.open("wb") as out:
            out.write(new_prefix)
            for ch in payload_chunks:
                out.write(ch)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_path, asar_path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------

def load_state(state_dir: Path) -> Dict[str, Any]:
    state_file = state_dir / "rtl-state.json"
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state_dir: Path, state: Dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "rtl-state.json"
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def file_signature(p: Path) -> Dict[str, int]:
    st = p.stat()
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


# ---------------------------------------------------------------------------
# Desktop App (Antigravity 2.0) Patcher & Restorer
# ---------------------------------------------------------------------------

def is_desktop_asar_patched(asar_path: Path) -> bool:
    if not asar_path.exists():
        return False
    header, payload_start = parse_asar_header(asar_path)
    pkg_raw = read_asar_text_file(asar_path, header, payload_start, "package.json")
    if not pkg_raw:
        return False
    main_rel = json.loads(pkg_raw).get("main", "dist/main.js").lstrip("./")
    main_txt = read_asar_text_file(asar_path, header, payload_start, main_rel) or ""
    return JS_START in main_txt


def patch_desktop(desktop_dir: Path, state_dir: Path, force: bool = False) -> Tuple[bool, str]:
    asar_path = desktop_dir / "resources" / "app.asar"
    exe_path = find_desktop_executable(desktop_dir)
    if not asar_path.exists():
        return False, f"Desktop app.asar not found at {asar_path}"

    if is_asar_integrity_fuse_enabled(exe_path):
        exe_name = exe_path.name if exe_path else "Antigravity"
        return False, f"Skipped Desktop patch: EnableEmbeddedAsarIntegrityValidation fuse is active on {exe_name}"

    css_text, js_text, payload_hash = load_assets()
    state = load_state(state_dir)
    desk_state = state.get("desktop", {})

    if not force and desk_state.get("payload_hash") == payload_hash:
        sig = file_signature(asar_path)
        if desk_state.get("asar_sig") == sig:
            return True, "Desktop already patched (fast cache hit)"

    header, payload_start = parse_asar_header(asar_path)
    pkg_raw = read_asar_text_file(asar_path, header, payload_start, "package.json")
    if not pkg_raw:
        return False, "package.json missing inside app.asar"

    pkg = json.loads(pkg_raw)
    main_rel = pkg.get("main", "dist/main.js").lstrip("./").replace("\\", "/")
    main_txt = read_asar_text_file(asar_path, header, payload_start, main_rel)
    if main_txt is None:
        return False, f"Main entry {main_rel} not found inside app.asar"

    preload_paths = find_asar_preload_paths(header)
    if not preload_paths:
        return False, "preload.js not found inside app.asar"

    already_marked = JS_START in main_txt
    if already_marked and not force and desk_state.get("payload_hash") == payload_hash:
        state["desktop"] = {
            "version": pkg.get("version", ""),
            "payload_hash": payload_hash,
            "asar_sig": file_signature(asar_path),
        }
        save_state(state_dir, state)
        return True, f"Desktop v{pkg.get('version', '?')} already patched"

    bak_path = asar_path.with_name("app.asar.orig.bak")
    if not already_marked:
        shutil.copy2(asar_path, bak_path)

    clean_main = strip_marked_block(main_txt, JS_START, JS_END)
    patched_main = clean_main + build_main_js_snippet(css_text)

    replacements: Dict[str, bytes] = {
        main_rel: patched_main.encode("utf-8"),
    }

    preload_snippet = build_preload_js_snippet(css_text, js_text)
    for pre_rel in preload_paths:
        pre_txt = read_asar_text_file(asar_path, header, payload_start, pre_rel)
        if pre_txt is not None:
            clean_pre = strip_marked_block(pre_txt, JS_START, JS_END)
            replacements[pre_rel] = (clean_pre + preload_snippet).encode("utf-8")

    try:
        rebuild_asar_with_replacements(asar_path, replacements)
    except PermissionError:
        return False, "LOCKED: Antigravity.exe is currently running and locking app.asar. Close Antigravity first."

    state["desktop"] = {
        "version": pkg.get("version", ""),
        "payload_hash": payload_hash,
        "asar_sig": file_signature(asar_path),
    }
    save_state(state_dir, state)
    return True, f"Patched Antigravity Desktop v{pkg.get('version', '?')} ({main_rel} + {', '.join(preload_paths)})"


def restore_desktop(desktop_dir: Path, state_dir: Path) -> Tuple[bool, str]:
    asar_path = desktop_dir / "resources" / "app.asar"
    bak_path = asar_path.with_name("app.asar.orig.bak")
    if not asar_path.exists():
        return False, f"Desktop app.asar not found at {asar_path}"

    try:
        if bak_path.exists():
            shutil.copy2(bak_path, asar_path)
            bak_path.unlink()
            msg = "Restored Desktop app.asar from clean backup (app.asar.orig.bak)"
        else:
            header, payload_start = parse_asar_header(asar_path)
            pkg_raw = read_asar_text_file(asar_path, header, payload_start, "package.json") or "{}"
            main_rel = json.loads(pkg_raw).get("main", "dist/main.js").lstrip("./").replace("\\", "/")
            replacements: Dict[str, bytes] = {}
            main_txt = read_asar_text_file(asar_path, header, payload_start, main_rel)
            if main_txt and JS_START in main_txt:
                replacements[main_rel] = strip_marked_block(main_txt, JS_START, JS_END).encode("utf-8")
            for pre_rel in find_asar_preload_paths(header):
                pre_txt = read_asar_text_file(asar_path, header, payload_start, pre_rel)
                if pre_txt and JS_START in pre_txt:
                    replacements[pre_rel] = strip_marked_block(pre_txt, JS_START, JS_END).encode("utf-8")
            if replacements:
                rebuild_asar_with_replacements(asar_path, replacements)
                msg = "Stripped RTL patch markers from Desktop app.asar"
            else:
                msg = "Desktop app.asar was already unpatched"
    except PermissionError:
        return False, "LOCKED: Antigravity.exe is currently running and locking app.asar. Close Antigravity first."

    state = load_state(state_dir)
    state.pop("desktop", None)
    save_state(state_dir, state)
    return True, msg


# ---------------------------------------------------------------------------
# Antigravity IDE (VS Code-based) Patcher & Restorer
# ---------------------------------------------------------------------------

def find_ide_targets(ide_dir: Path) -> Tuple[List[Path], List[Path]]:
    app_root = ide_dir / "resources" / "app"
    html_targets: List[Path] = []
    css_targets: List[Path] = []
    if not app_root.exists():
        return html_targets, css_targets

    vs_code_dir = app_root / "out" / "vs" / "code"
    if vs_code_dir.exists():
        for p in vs_code_dir.rglob("workbench*.html"):
            html_targets.append(p)

    for rel_css in ["out/jetskiMain.tailwind.css"]:
        cp = app_root / rel_css
        if cp.exists():
            css_targets.append(cp)

    return sorted(html_targets), sorted(css_targets)


def patch_ide(ide_dir: Path, state_dir: Path, force: bool = False) -> Tuple[bool, str]:
    app_root = ide_dir / "resources" / "app"
    if not app_root.exists():
        return False, f"Antigravity IDE app directory not found at {app_root}"

    html_targets, css_targets = find_ide_targets(ide_dir)
    if not html_targets:
        return False, f"No workbench*.html files found in {app_root}"

    css_text, js_text, payload_hash = load_assets()
    state = load_state(state_dir)
    ide_state = state.get("ide", {})

    tracked_files = html_targets + css_targets
    if not force and ide_state.get("payload_hash") == payload_hash:
        sigs = {str(p): file_signature(p) for p in tracked_files}
        if ide_state.get("file_sigs") == sigs:
            return True, "IDE already patched (fast cache hit)"

    html_injection = (
        f"\n\t{HTML_START}\n"
        '\t<link rel="stylesheet" href="./agy-rtl.css" />\n'
        '\t<script src="./agy-rtl.js"></script>\n'
        f"\t{HTML_END}\n"
    )

    try:
        for html_file in html_targets:
            txt = html_file.read_text(encoding="utf-8")
            bak = html_file.with_name(html_file.name + ".orig.bak")
            if HTML_START not in txt:
                shutil.copy2(html_file, bak)
            clean_txt = strip_marked_block(txt, HTML_START, HTML_END)
            if "</head>" in clean_txt:
                patched_txt = clean_txt.replace("</head>", f"{html_injection}</head>", 1)
            else:
                patched_txt = clean_txt + html_injection
            html_file.write_text(patched_txt, encoding="utf-8")

            (html_file.parent / "agy-rtl.css").write_text(css_text, encoding="utf-8")
            (html_file.parent / "agy-rtl.js").write_text(js_text, encoding="utf-8")

        for css_file in css_targets:
            txt = css_file.read_text(encoding="utf-8")
            bak = css_file.with_name(css_file.name + ".orig.bak")
            if CSS_START not in txt:
                shutil.copy2(css_file, bak)
            clean_txt = strip_marked_block(txt, CSS_START, CSS_END)
            patched_css = f"{clean_txt}\n{CSS_START}\n{css_text}\n{CSS_END}\n"
            css_file.write_text(patched_css, encoding="utf-8")
    except PermissionError:
        return False, "LOCKED: Antigravity IDE files are locked. Close Antigravity IDE and retry."

    state["ide"] = {
        "payload_hash": payload_hash,
        "file_sigs": {str(p): file_signature(p) for p in tracked_files},
    }
    save_state(state_dir, state)
    return True, f"Patched Antigravity IDE ({len(html_targets)} HTML + {len(css_targets)} CSS files)"


def restore_ide(ide_dir: Path, state_dir: Path) -> Tuple[bool, str]:
    app_root = ide_dir / "resources" / "app"
    if not app_root.exists():
        return False, f"Antigravity IDE not found at {app_root}"

    html_targets, css_targets = find_ide_targets(ide_dir)
    restored_count = 0
    try:
        for html_file in html_targets:
            bak = html_file.with_name(html_file.name + ".orig.bak")
            if bak.exists():
                shutil.copy2(bak, html_file)
                bak.unlink()
                restored_count += 1
            else:
                txt = html_file.read_text(encoding="utf-8")
                if HTML_START in txt:
                    html_file.write_text(strip_marked_block(txt, HTML_START, HTML_END), encoding="utf-8")
                    restored_count += 1
            for sidecar in ("agy-rtl.css", "agy-rtl.js"):
                sp = html_file.parent / sidecar
                if sp.exists():
                    sp.unlink()

        for css_file in css_targets:
            bak = css_file.with_name(css_file.name + ".orig.bak")
            if bak.exists():
                shutil.copy2(bak, css_file)
                bak.unlink()
                restored_count += 1
            else:
                txt = css_file.read_text(encoding="utf-8")
                if CSS_START in txt:
                    css_file.write_text(strip_marked_block(txt, CSS_START, CSS_END), encoding="utf-8")
                    restored_count += 1
    except PermissionError:
        return False, "LOCKED: Close Antigravity IDE before restoring."

    state = load_state(state_dir)
    state.pop("ide", None)
    save_state(state_dir, state)
    return True, f"Restored Antigravity IDE ({restored_count} files)"


# ---------------------------------------------------------------------------
# Windows Shortcut Installer / Restorer (Smart Launcher + Visible RTL Icons)
# ---------------------------------------------------------------------------

def resolve_windows_special_dirs() -> Tuple[Path, Path]:
    fallback_desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    fallback_programs = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if sys.platform != "win32":
        return fallback_desktop, fallback_programs
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                "[Environment]::GetFolderPath('Desktop'); "
                "[Environment]::GetFolderPath('Programs')",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        if len(lines) >= 2:
            return Path(lines[0]), Path(lines[1])
    except Exception:
        pass
    return fallback_desktop, fallback_programs


def get_shortcut_definitions(desktop_dir: Path, ide_dir: Path) -> List[Dict[str, Any]]:
    user_desktop, start_menu = resolve_windows_special_dirs()
    defs: List[Dict[str, Any]] = []

    desk_exe = desktop_dir / "Antigravity.exe"
    if desk_exe.exists():
        vbs = SCRIPT_DIR / "launch-desktop.vbs"
        # Dedicated visible RTL shortcuts (never overwritten by NSIS updates!)
        defs.append({
            "key": "desktop_dedicated_desk",
            "lnk": user_desktop / "Antigravity RTL.lnk",
            "vbs": vbs,
            "exe": desk_exe,
            "workdir": desktop_dir,
            "dedicated": True,
            "desc": "Antigravity (Smart Persian RTL + Vazirmatn Launcher)",
        })
        defs.append({
            "key": "desktop_dedicated_menu",
            "lnk": start_menu / "Antigravity RTL.lnk",
            "vbs": vbs,
            "exe": desk_exe,
            "workdir": desktop_dir,
            "dedicated": True,
            "desc": "Antigravity (Smart Persian RTL + Vazirmatn Launcher)",
        })
        # Existing standard shortcuts
        for tag, lnk in [("desktop_orig_desk", user_desktop / "Antigravity.lnk"), ("desktop_orig_menu", start_menu / "Antigravity.lnk")]:
            defs.append({
                "key": tag,
                "lnk": lnk,
                "vbs": vbs,
                "exe": desk_exe,
                "workdir": desktop_dir,
                "dedicated": False,
                "desc": "Antigravity (Smart Persian RTL + Vazirmatn Launcher)",
            })

    ide_exe = ide_dir / "Antigravity IDE.exe"
    if ide_exe.exists():
        vbs = SCRIPT_DIR / "launch-ide.vbs"
        defs.append({
            "key": "ide_dedicated_desk",
            "lnk": user_desktop / "Antigravity IDE RTL.lnk",
            "vbs": vbs,
            "exe": ide_exe,
            "workdir": ide_dir,
            "dedicated": True,
            "desc": "Antigravity IDE (Smart Persian RTL + Vazirmatn Launcher)",
        })
        for tag, lnk in [
            ("ide_orig_desk", user_desktop / "Antigravity IDE.lnk"),
            ("ide_orig_menu", start_menu / "Antigravity" / "Antigravity IDE.lnk"),
        ]:
            defs.append({
                "key": tag,
                "lnk": lnk,
                "vbs": vbs,
                "exe": ide_exe,
                "workdir": ide_dir,
                "dedicated": False,
                "desc": "Antigravity IDE (Smart Persian RTL + Vazirmatn Launcher)",
            })
    return defs


def resolve_linux_shortcut_dirs() -> Tuple[Path, Optional[Path]]:
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    apps_dir = xdg_data / "applications"
    desktop_dir = Path.home() / "Desktop"
    return apps_dir, desktop_dir if desktop_dir.is_dir() else None


def _build_linux_desktop_entry(name: str, exec_cmd: str, icon: str, wm_class: str, comment: str) -> str:
    return (
        "[Desktop Entry]\n"
        f"Name={name}\n"
        f"Comment={comment}\n"
        f"Exec={exec_cmd}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Categories=Development;IDE;\n"
        f"StartupWMClass={wm_class}\n"
    )


def install_linux_shortcuts(
    desktop_dir: Path,
    ide_dir: Path,
    state_dir: Path,
    apps_dir: Optional[Path] = None,
    user_desktop_dir: Optional[Path] = None,
) -> Tuple[bool, str]:
    default_apps, default_desk = resolve_linux_shortcut_dirs()
    apps_dir = apps_dir or default_apps
    user_desktop_dir = user_desktop_dir if user_desktop_dir is not None else default_desk

    apps_dir.mkdir(parents=True, exist_ok=True)
    created: List[str] = []
    py_script = str(SCRIPT_DIR / "antigravity_rtl.py")

    if find_desktop_executable(desktop_dir):
        icon = find_linux_app_icon(desktop_dir, is_ide=False)
        exec_cmd = (
            f"python3 {shlex.quote(py_script)} launch desktop "
            f"--desktop-dir {shlex.quote(str(desktop_dir))} "
            f"--state-dir {shlex.quote(str(state_dir))} -- %F"
        )
        content = _build_linux_desktop_entry(
            name="Antigravity RTL",
            exec_cmd=exec_cmd,
            icon=icon,
            wm_class="Antigravity",
            comment="Antigravity (Smart Persian RTL + Vazirmatn Launcher)",
        )
        for target in [apps_dir / "antigravity-rtl.desktop"] + (
            [user_desktop_dir / "antigravity-rtl.desktop"] if user_desktop_dir else []
        ):
            target.write_text(content, encoding="utf-8")
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            created.append(str(target))

    if find_ide_executable(ide_dir):
        icon = find_linux_app_icon(ide_dir, is_ide=True)
        exec_cmd = (
            f"python3 {shlex.quote(py_script)} launch ide "
            f"--ide-dir {shlex.quote(str(ide_dir))} "
            f"--state-dir {shlex.quote(str(state_dir))} -- %F"
        )
        content = _build_linux_desktop_entry(
            name="Antigravity IDE RTL",
            exec_cmd=exec_cmd,
            icon=icon,
            wm_class="Antigravity",
            comment="Antigravity IDE (Smart Persian RTL + Vazirmatn Launcher)",
        )
        for target in [apps_dir / "antigravity-ide-rtl.desktop"] + (
            [user_desktop_dir / "antigravity-ide-rtl.desktop"] if user_desktop_dir else []
        ):
            target.write_text(content, encoding="utf-8")
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            created.append(str(target))

    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(apps_dir)], capture_output=True)

    if not created:
        return False, "No Antigravity executable found to create Linux shortcuts."
    return True, f"Created Linux .desktop shortcuts: {', '.join(created)}"


def restore_linux_shortcuts(
    apps_dir: Optional[Path] = None,
    user_desktop_dir: Optional[Path] = None,
) -> Tuple[bool, str]:
    default_apps, default_desk = resolve_linux_shortcut_dirs()
    apps_dir = apps_dir or default_apps
    user_desktop_dir = user_desktop_dir if user_desktop_dir is not None else default_desk

    removed = 0
    names = ("antigravity-rtl.desktop", "antigravity-ide-rtl.desktop")
    dirs = [apps_dir] + ([user_desktop_dir] if user_desktop_dir else [])
    for d in dirs:
        for name in names:
            p = d / name
            if p.exists():
                p.unlink()
                removed += 1

    if shutil.which("update-desktop-database") and apps_dir.exists():
        subprocess.run(["update-desktop-database", str(apps_dir)], capture_output=True)

    return True, f"Removed {removed} Linux RTL .desktop shortcut(s)"


def install_shortcuts(desktop_dir: Path, ide_dir: Path, state_dir: Path) -> Tuple[bool, str]:
    if sys.platform.startswith("linux"):
        return install_linux_shortcuts(desktop_dir, ide_dir, state_dir)
    if sys.platform != "win32":
        return False, "Shortcut installation is only supported on Windows and Linux."

    backup_dir = state_dir / "shortcut_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    defs = get_shortcut_definitions(desktop_dir, ide_dir)
    created_paths: List[str] = []

    wscript_exe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe"

    for item in defs:
        lnk: Path = item["lnk"]
        if not lnk.parent.exists():
            continue
        if not item["dedicated"]:
            bak_lnk = backup_dir / f"{item['key']}__{lnk.name}"
            if lnk.exists() and not bak_lnk.exists():
                shutil.copy2(lnk, bak_lnk)

        lnk_esc = str(lnk).replace("'", "''")
        ws_esc = str(wscript_exe).replace("'", "''")
        vbs_esc = str(item["vbs"]).replace("'", "''")
        wd_esc = str(item["workdir"]).replace("'", "''")
        exe_esc = str(item["exe"]).replace("'", "''")
        desc_esc = str(item["desc"]).replace("'", "''")

        ps_cmd = (
            "$sh = New-Object -ComObject WScript.Shell; "
            f"$s = $sh.CreateShortcut('{lnk_esc}'); "
            f"$s.TargetPath = '{ws_esc}'; "
            f"$s.Arguments = '//B //Nologo \"' + '{vbs_esc}' + '\"'; "
            f"$s.WorkingDirectory = '{wd_esc}'; "
            f"$s.IconLocation = '{exe_esc},0'; "
            f"$s.Description = '{desc_esc}'; "
            "$s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            check=True,
            capture_output=True,
        )
        if item["dedicated"] and "Desktop" in str(lnk.parent):
            created_paths.append(str(lnk))

    summary = f"Created Desktop shortcuts: {', '.join(created_paths)}" if created_paths else "Shortcuts configured"
    return True, summary


def restore_shortcuts(desktop_dir: Path, ide_dir: Path, state_dir: Path) -> Tuple[bool, str]:
    if sys.platform.startswith("linux"):
        return restore_linux_shortcuts()
    if sys.platform != "win32":
        return False, "Shortcut restore is only supported on Windows and Linux."

    backup_dir = state_dir / "shortcut_backups"
    defs = get_shortcut_definitions(desktop_dir, ide_dir)
    restored = 0

    for item in defs:
        lnk: Path = item["lnk"]
        if item["dedicated"]:
            if lnk.exists():
                lnk.unlink()
                restored += 1
            continue

        bak_lnk = backup_dir / f"{item['key']}__{lnk.name}"
        if bak_lnk.exists():
            shutil.copy2(bak_lnk, lnk)
            bak_lnk.unlink()
            restored += 1
        elif lnk.exists():
            lnk_esc = str(lnk).replace("'", "''")
            exe_esc = str(item["exe"]).replace("'", "''")
            wd_esc = str(item["workdir"]).replace("'", "''")
            ps_cmd = (
                "$sh = New-Object -ComObject WScript.Shell; "
                f"$s = $sh.CreateShortcut('{lnk_esc}'); "
                f"$s.TargetPath = '{exe_esc}'; "
                "$s.Arguments = ''; "
                f"$s.WorkingDirectory = '{wd_esc}'; "
                f"$s.IconLocation = '{exe_esc},0'; "
                "$s.Save()"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                check=True,
                capture_output=True,
            )
            restored += 1

    return True, f"Removed dedicated RTL shortcuts and restored {restored} original shortcuts"


# ---------------------------------------------------------------------------
# Smart Launcher Execution
# ---------------------------------------------------------------------------

def launch_app(which: str, desktop_dir: Path, ide_dir: Path, state_dir: Path, extra_args: List[str]) -> int:
    if which == "desktop":
        patch_desktop(desktop_dir, state_dir, force=False)
        wrapper = None if sys.platform == "win32" else find_wrapper_for_dir("antigravity", desktop_dir)
        exe = wrapper or find_desktop_executable(desktop_dir)
        cwd = desktop_dir
    elif which == "ide":
        patch_ide(ide_dir, state_dir, force=False)
        wrapper = None if sys.platform == "win32" else find_wrapper_for_dir("antigravity-ide", ide_dir)
        exe = wrapper or find_ide_executable(ide_dir)
        cwd = ide_dir
    else:
        raise ValueError(f"Unknown launch target: {which}")

    if not exe or not exe.exists():
        return 1

    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [str(exe), *extra_args],
            cwd=str(cwd),
            close_fds=True,
            creationflags=creationflags,
        )
    else:
        subprocess.Popen(
            [str(exe), *extra_args],
            cwd=str(cwd),
            close_fds=True,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return 0


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Antigravity Persian RTL & Vazirmatn Smart Patcher")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for cmd_name in ("patch", "restore", "status"):
        p = sub.add_parser(cmd_name)
        p.add_argument("--target", choices=["all", "desktop", "ide"], default="all")
        p.add_argument("--desktop-dir", type=Path, default=default_desktop_dir())
        p.add_argument("--ide-dir", type=Path, default=default_ide_dir())
        p.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
        if cmd_name == "patch":
            p.add_argument("--force", action="store_true", help="Re-apply patch even if state matches")
            p.add_argument("--no-shortcuts", action="store_true", help="Skip creating Desktop/Start Menu shortcuts")

    p_launch = sub.add_parser("launch")
    p_launch.add_argument("which", choices=["desktop", "ide"])
    p_launch.add_argument("--desktop-dir", type=Path, default=default_desktop_dir())
    p_launch.add_argument("--ide-dir", type=Path, default=default_ide_dir())
    p_launch.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    p_launch.add_argument("extra_args", nargs=argparse.REMAINDER)

    for sc_cmd in ("install-shortcuts", "restore-shortcuts"):
        ps = sub.add_parser(sc_cmd)
        ps.add_argument("--desktop-dir", type=Path, default=default_desktop_dir())
        ps.add_argument("--ide-dir", type=Path, default=default_ide_dir())
        ps.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)

    args = parser.parse_args(argv)

    if args.cmd == "launch":
        extra = list(args.extra_args)
        if extra and extra[0] == "--":
            extra = extra[1:]
        return launch_app(args.which, args.desktop_dir, args.ide_dir, args.state_dir, extra)

    if args.cmd == "install-shortcuts":
        ok, msg = install_shortcuts(args.desktop_dir, args.ide_dir, args.state_dir)
        print(f"[Shortcuts] {msg}")
        return 0 if ok else 1

    if args.cmd == "restore-shortcuts":
        ok, msg = restore_shortcuts(args.desktop_dir, args.ide_dir, args.state_dir)
        print(f"[Shortcuts] {msg}")
        return 0 if ok else 1

    if args.cmd == "status":
        asar = args.desktop_dir / "resources" / "app.asar"
        print(f"Desktop ({args.desktop_dir}): {'PATCHED' if is_desktop_asar_patched(asar) else 'UNPATCHED'}")
        htmls, _ = find_ide_targets(args.ide_dir)
        ide_patched = bool(htmls) and all(HTML_START in h.read_text(encoding="utf-8") for h in htmls)
        print(f"IDE     ({args.ide_dir}): {'PATCHED' if ide_patched else 'UNPATCHED'}")
        return 0

    exit_code = 0
    if args.cmd == "patch":
        if not args.no_shortcuts and (sys.platform == "win32" or sys.platform.startswith("linux")):
            sc_ok, sc_msg = install_shortcuts(args.desktop_dir, args.ide_dir, args.state_dir)
            print(f"[Shortcuts] {sc_msg}")
            if not sc_ok:
                exit_code = 2
        if args.target in ("all", "desktop") and args.desktop_dir.exists():
            ok, msg = patch_desktop(args.desktop_dir, args.state_dir, force=args.force)
            print(f"[Desktop]   {msg}")
            if not ok:
                exit_code = 2
        if args.target in ("all", "ide") and args.ide_dir.exists():
            ok, msg = patch_ide(args.ide_dir, args.state_dir, force=args.force)
            print(f"[IDE]       {msg}")
            if not ok:
                exit_code = 2
        return exit_code

    if args.cmd == "restore":
        if args.target in ("all", "desktop") and args.desktop_dir.exists():
            ok, msg = restore_desktop(args.desktop_dir, args.state_dir)
            print(f"[Desktop]   {msg}")
            if not ok:
                exit_code = 2
        if args.target in ("all", "ide") and args.ide_dir.exists():
            ok, msg = restore_ide(args.ide_dir, args.state_dir)
            print(f"[IDE]       {msg}")
            if not ok:
                exit_code = 2
        return exit_code

    return 0


if __name__ == "__main__":
    sys.exit(main())
