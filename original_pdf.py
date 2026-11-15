#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  PDF BUILDER PRO  v1.0
================================================================================
A professional terminal-based PDF creation, customization, validation and
packaging tool.

Features
--------
  * Create new PDFs or work on an existing PDF (original is never modified)
  * Visible custom page text (max 1,000 chars, min 100 words, auto-wrapping)
  * Full customization: metadata, headers, footers, watermarks, page numbers,
    background color, fonts, alignment, positioning, page size/orientation
  * Import batch / JavaScript source files as INERT TXT attachments
    (NEVER executed, NEVER embedded as active PDF JavaScript)
  * Attach safe documents and extract them again
  * PDF validation (header, integrity, page count, metadata, attachments)
  * Export with verification, logging and automatic temp cleanup

Installation
------------
    pip install reportlab pypdf colorama

Run
---
    python pdf_builder_pro.py

Notes
-----
  * Nothing is ever downloaded, launched or executed by this tool.
  * Imported batch / JS files are only ever stored as inert TXT attachments.
================================================================================
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import io
import os
import re
import sys
import shutil
import datetime
import traceback

# ---------------------------- ANSI colour support -----------------------------
_ANSI_OK = True
if os.name == "nt":                      # Windows: try colorama first
    try:
        import colorama
        colorama.init()
    except ImportError:
        _ANSI_OK = False

if _ANSI_OK:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
else:
    RESET = BOLD = DIM = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ""

# ------------------------------ Dependency: reportlab -------------------------
try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4, LETTER, LEGAL
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import simpleSplit
    HAS_REPORTLAB = True
except Exception:                                          # pragma: no cover
    rl_canvas = None
    A4 = (595.2755905511812, 841.8897637795277)
    LETTER = (612.0, 792.0)
    LEGAL = (612.0, 1008.0)
    HexColor = None
    simpleSplit = None
    HAS_REPORTLAB = False

# ------------------------------ Dependency: pypdf -----------------------------
try:
    from pypdf import PdfReader, PdfWriter
    PDF_LIB = "pypdf"
    HAS_PYPDF = True
except Exception:                                          # pragma: no cover
    try:
        from PyPDF2 import PdfReader, PdfWriter
        PDF_LIB = "PyPDF2"
        HAS_PYPDF = True
    except Exception:
        PdfReader = None
        PdfWriter = None
        PDF_LIB = None
        HAS_PYPDF = False


# ==============================================================================
# DIRECTORY / FILE LAYOUT
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.join(BASE_DIR, "PDF_BUILDER_PRO")

DIRS = {
    "output":      os.path.join(APP_ROOT, "output"),
    "logs":        os.path.join(APP_ROOT, "logs"),
    "attachments": os.path.join(APP_ROOT, "attachments"),
    "temp":        os.path.join(APP_ROOT, "temp"),
    "previews":    os.path.join(APP_ROOT, "previews"),
}
LOG_FILE = os.path.join(DIRS["logs"], "debug.log")

PAGE_SIZES = {"A4": A4, "LETTER": LETTER, "LEGAL": LEGAL}

FONT_CHOICES = {
    "1": "Helvetica",
    "2": "Helvetica-Bold",
    "3": "Times-Roman",
    "4": "Times-Bold",
    "5": "Courier",
    "6": "Courier-Bold",
}

SAFE_ATTACHMENT_EXT = {
    ".txt", ".log", ".csv", ".md", ".json", ".xml", ".html", ".htm",
    ".bat", ".cmd", ".js", ".py", ".sh", ".ini", ".cfg", ".yml", ".yaml",
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
}


# ==============================================================================
# GLOBAL APPLICATION STATE
# ==============================================================================
STATE = {
    "source_pdf": None,       # working PDF (never modified in place)
    "original_pdf": None,     # original PDF path the user wants preserved
    "custom_text": "",        # visible text block
    "batch_code": None,       # imported batch source (inert)
    "js_source": None,        # imported JavaScript source (inert)
    "attachments": [],        # [{"name", "path", "data", "size"}]
    "output_dir": DIRS["output"],
    "output_name": "PDF_BUILDER_PRO_output.pdf",
    "custom": {
        "title": "",
        "author": "",
        "subject": "",
        "keywords": "",
        "page_numbers": True,
        "header_text": "",
        "footer_text": "",
        "watermark": "",
        "background": "#FFFFFF",
        "text_position": "center",     # top | center | bottom
        "font_name": "Helvetica",
        "font_size": 12,
        "align": "left",               # left | center | right
        "page_size": "A4",
        "orientation": "portrait",
        "text_width_margin": 50,
        "text_all_pages": True,
    },
}


# ==============================================================================
# SMALL UTILITIES
# ==============================================================================
def timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def setup_dirs():
    """Create the working folder structure, with permission checks."""
    for name, path in DIRS.items():
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as exc:                           # pragma: no cover
            print(f"{RED}[FATAL]{RESET} Cannot create {path}: {exc}")
            sys.exit(1)


def log(message, level="INFO"):
    """Append a line to debug.log (never raises)."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] [{level}] {message}\n")
    except Exception:
        pass


def info(msg):
    print(f"{CYAN}[i]{RESET} {msg}")


def ok(msg):
    print(f"{GREEN}[OK]{RESET} {msg}")


def warn(msg):
    print(f"{YELLOW}[!]{RESET} {msg}")


def err(msg):
    print(f"{RED}[X]{RESET} {msg}")


def header(title):
    bar = "=" * 62
    return f"\n{CYAN}{bar}{RESET}\n{BOLD}{CYAN}  {title}{RESET}\n{CYAN}{bar}{RESET}"


def pause():
    try:
        input(f"\n{DIM}  Press ENTER to continue...{RESET}")
    except (EOFError, KeyboardInterrupt):
        raise


def safe_input(prompt):
    """input() that converts EOF into a graceful shutdown."""
    try:
        return input(prompt)
    except EOFError:
        print()
        raise KeyboardInterrupt


def confirm(prompt, default=True):
    hint = "Y/n" if default else "y/N"
    raw = safe_input(f"  {prompt} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def ask_int(prompt, default, lo=None, hi=None):
    while True:
        raw = safe_input(f"  {prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            err("Please enter a whole number.")
            continue
        if lo is not None and value < lo:
            err(f"Value must be >= {lo}.")
            continue
        if hi is not None and value > hi:
            err(f"Value must be <= {hi}.")
            continue
        return value


def ask_choice(prompt, options, default):
    print(f"  {prompt}:")
    for idx, opt in enumerate(options, 1):
        print(f"    {idx}. {opt}")
    while True:
        raw = safe_input(f"  Choose 1-{len(options)} [default {default}]: ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        err("Invalid choice, try again.")


def clean_path(raw):
    """Strip quotes / whitespace and expand the user home marker."""
    if raw is None:
        return ""
    return os.path.expanduser(raw.strip().strip('"').strip("'"))


def is_valid_hex_color(value):
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", (value or "").strip()))


def cleanup_temp():
    """Delete everything inside the temp folder (best effort)."""
    try:
        for name in os.listdir(DIRS["temp"]):
            path = os.path.join(DIRS["temp"], name)
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
            except Exception:
                pass
    except Exception:
        pass


# ==============================================================================
# BANNER / MENU / DEPENDENCY CHECK
# ==============================================================================
def print_banner():
    banner = r"""
==============================================================
   ____  ____  _____    ____        _ _     _
  |  _ \|  _ \|  ___|  | __ ) _   _(_) | __| | ___ _ __
  | |_) | | | | |_     |  _ \| | | | | |/ _` |/ _ \ '__|
  |  __/| |_| |  _|    | |_) | |_| | | | (_| |  __/ |
  |_|   |____/|_|      |____/ \__,_|_|_|\__,_|\___|_|
                    P R O   v1.0
=============================================================="""
    print(CYAN + banner + RESET)
    print(f"{DIM}  Terminal PDF creation & packaging suite  |  "
          f"Library: {PDF_LIB or 'none'}{RESET}")


def print_menu():
    print(f"\n{BOLD}{WHITE}  MAIN MENU{RESET}")
    entries = [
        ("1",  "Create a new PDF"),
        ("2",  "Select an existing PDF"),
        ("3",  "Preview selected PDF"),
        ("4",  "Enter original PDF path"),
        ("5",  "Add custom page text"),
        ("6",  "Customize PDF appearance"),
        ("7",  "Import batch code from TXT"),
        ("8",  "Import JavaScript source from TXT"),
        ("9",  "Attach TXT files to PDF as inert attachments"),
        ("10", "PDF information and metadata"),
        ("11", "Validate PDF"),
        ("12", "Export final PDF"),
        ("13", "View logs"),
        ("14", "Settings"),
        ("0",  "Exit"),
    ]
    for key, label in entries:
        colour = YELLOW if key == "0" else GREEN
        print(f"   {colour}{key:>3}{RESET}  {label}")
    print(f"{DIM}  " + "-" * 58 + RESET)


def check_dependencies():
    print(header("DEPENDENCY CHECK"))
    deps = [
        ("reportlab", HAS_REPORTLAB, "pip install reportlab"),
        ("pypdf / PyPDF2", HAS_PYPDF, "pip install pypdf"),
    ]
    for name, present, hint in deps:
        if present:
            print(f"  {GREEN}[OK]{RESET}      {name}")
        else:
            print(f"  {RED}[MISSING]{RESET} {name}   ->  {hint}")
    if not HAS_REPORTLAB or not HAS_PYPDF:
        print()
        warn("Some features are disabled until the missing packages are "
             "installed. The application will still run.")
    print()


# ==============================================================================
# PDF HELPERS
# ==============================================================================
def pdf_page_count(path):
    try:
        reader = PdfReader(path)
        return len(reader.pages)
    except Exception:
        return None


def read_pdf_metadata(path):
    try:
        reader = PdfReader(path)
        meta = reader.metadata or {}
        result = {}
        for key, value in dict(meta).items():
            try:
                result[str(key)] = str(value)
            except Exception:
                result[str(key)] = "<unreadable>"
        return result
    except Exception as exc:
        log(f"Metadata read failed for {path}: {exc}", "ERROR")
        return {}


def extract_text_snippet(path, max_chars=600):
    try:
        reader = PdfReader(path)
        if not reader.pages:
            return ""
        text = reader.pages[0].extract_text() or ""
        text = text.strip()
        return text[:max_chars]
    except Exception as exc:
        return f"[text extraction failed: {exc}]"


def list_pdf_attachments(path):
    try:
        reader = PdfReader(path)
        attachments = getattr(reader, "attachments", None)
        if attachments is None:
            return {}
        out = {}
        for name, data in attachments.items():
            try:
                if isinstance(data, (list, tuple)) and data:
                    payload = data[0]
                else:
                    payload = data
                out[name] = len(payload) if hasattr(payload, "__len__") else 0
            except Exception:
                out[name] = 0
        return out
    except Exception:
        return {}


def human_size(num_bytes):
    try:
        size = float(num_bytes)
    except Exception:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"


def describe_pdf(path):
    """Return a dict with filename/size/pages/metadata or None if unreadable."""
    if not os.path.isfile(path):
        return None
    try:
        size = os.path.getsize(path)
    except Exception:
        size = 0
    return {
        "path": path,
        "name": os.path.basename(path),
        "size": size,
        "pages": pdf_page_count(path),
        "metadata": read_pdf_metadata(path),
        "attachments": list_pdf_attachments(path),
    }


def print_pdf_description(desc):
    print(f"  {BOLD}File      :{RESET} {desc['name']}")
    print(f"  {BOLD}Path      :{RESET} {desc['path']}")
    print(f"  {BOLD}Size      :{RESET} {human_size(desc['size'])} "
          f"({desc['size']} bytes)")
    pages = desc["pages"]
    if pages is None:
        print(f"  {BOLD}Pages     :{RESET} {RED}unreadable{RESET}")
    else:
        print(f"  {BOLD}Pages     :{RESET} {pages}")
    meta = desc["metadata"]
    if meta:
        print(f"  {BOLD}Metadata  :{RESET}")
        for key, value in meta.items():
            short = value if len(value) <= 70 else value[:67] + "..."
            print(f"      {DIM}{key}{RESET}: {short}")
    else:
        print(f"  {BOLD}Metadata  :{RESET} {DIM}(none){RESET}")
    att = desc["attachments"]
    if att:
        print(f"  {BOLD}Attachments:{RESET}")
        for name, size in att.items():
            print(f"      {name}  ({human_size(size)})")
    else:
        print(f"  {BOLD}Attachments:{RESET} {DIM}(none){RESET}")


# ==============================================================================
# 1. CREATE A NEW PDF
# ==============================================================================
def do_create_new_pdf():
    print(header("CREATE A NEW PDF"))
    if not HAS_REPORTLAB:
        err("reportlab is required. Install it with: pip install reportlab")
        return

    pages = ask_int("Number of pages", 1, 1, 500)
    size_name = ask_choice("Page size", ["A4", "LETTER", "LEGAL"], "A4")
    orientation = ask_choice("Orientation", ["portrait", "landscape"], "portrait")

    width, height = PAGE_SIZES[size_name]
    if orientation == "landscape":
        width, height = height, width

    out_path = os.path.join(DIRS["temp"], f"new_base_{timestamp()}.pdf")
    try:
        canv = rl_canvas.Canvas(out_path, pagesize=(width, height))
        for _ in range(pages):
            canv.showPage()
        canv.save()
    except Exception as exc:
        err(f"Could not create the blank PDF: {exc}")
        log(traceback.format_exc(), "ERROR")
        return

    STATE["source_pdf"] = out_path
    STATE["custom"]["page_size"] = size_name
    STATE["custom"]["orientation"] = orientation
    log(f"Created new blank PDF: {out_path} ({pages} pages)")

    ok(f"New PDF created ({pages} pages, {size_name}, {orientation}).")
    info(f"Working copy: {out_path}")
    info("It now becomes the active document for the session.")


# ==============================================================================
# 2. SELECT AN EXISTING PDF
# ==============================================================================
def do_select_pdf():
    print(header("SELECT AN EXISTING PDF"))
    raw = safe_input("  PDF file path: ")
    path = clean_path(raw)
    if not path:
        warn("No path entered.")
        return

    if not os.path.exists(path):
        err("That path does not exist.")
        log(f"Select failed, missing file: {path}", "ERROR")
        return
    if not os.path.isfile(path):
        err("That path is not a file.")
        return
    if not os.access(path, os.R_OK):
        err("Permission denied: the file is not readable.")
        return
    if not path.lower().endswith(".pdf"):
        warn("The file does not end with .pdf - trying anyway.")

    try:
        with open(path, "rb") as fh:
            magic = fh.read(5)
    except Exception as exc:
        err(f"Cannot read the file: {exc}")
        return
    if not magic.startswith(b"%PDF"):
        err("This does not look like a PDF (missing %PDF header).")
        log(f"Invalid PDF header for {path}", "ERROR")
        return

    if not HAS_PYPDF:
        err("pypdf is required to open PDFs. Install: pip install pypdf")
        return

    desc = describe_pdf(path)
    if desc is None or desc["pages"] is None:
        err("The PDF could not be parsed.")
        return

    STATE["source_pdf"] = path
    log(f"Selected PDF: {path}")

    ok("PDF selected successfully.")
    print()
    print_pdf_description(desc)

    if confirm("Show a text preview of page 1?", default=False):
        snippet = extract_text_snippet(path)
        print(f"\n{DIM}--- page 1 text ---{RESET}")
        print(snippet if snippet else "(no extractable text - possibly scanned)")
        print(f"{DIM}--- end ---{RESET}")


# ==============================================================================
# 3. PREVIEW SELECTED PDF
# ==============================================================================
def do_preview_pdf():
    print(header("PREVIEW SELECTED PDF"))
    path = STATE["source_pdf"]
    if not path or not os.path.isfile(path):
        warn("No PDF selected. Use option 2 or 1 first.")
        return
    if not HAS_PYPDF:
        err("pypdf is required. Install: pip install pypdf")
        return

    desc = describe_pdf(path)
    print_pdf_description(desc)

    print(f"\n{BOLD}  Page 1 text preview{RESET}")
    snippet = extract_text_snippet(path, 900)
    print("  " + (snippet if snippet else "(no extractable text)").replace("\n", "\n  "))

    if STATE["custom_text"]:
        print(f"\n{BOLD}  Pending custom text block ({len(STATE['custom_text'])} chars)"
              f"{RESET}")
        print("  " + STATE["custom_text"][:400].replace("\n", "\n  "))
    else:
        print(f"\n{DIM}  No custom text block defined yet.{RESET}")


# ==============================================================================
# 4. ENTER ORIGINAL PDF PATH
# ==============================================================================
def do_enter_original_path():
    print(header("ENTER ORIGINAL PDF PATH"))
    info("The original PDF is NEVER modified - it is only used as a base.")
    raw = safe_input("  Original PDF path: ")
    path = clean_path(raw)
    if not path or not os.path.isfile(path):
        err("File not found.")
        return
    try:
        with open(path, "rb") as fh:
            magic = fh.read(5)
    except Exception as exc:
        err(f"Cannot read: {exc}")
        return
    if not magic.startswith(b"%PDF"):
        err("Not a valid PDF (bad header).")
        return

    STATE["original_pdf"] = path
    if not STATE["source_pdf"]:
        STATE["source_pdf"] = path
        info("No working PDF was set - the original becomes the working copy.")
    log(f"Original PDF registered: {path}")

    ok("Original PDF registered (kept untouched).")
    print(f"  {BOLD}Original :{RESET} {path}")
    print(f"  {BOLD}Working  :{RESET} {STATE['source_pdf']}")


# ==============================================================================
# 5. CUSTOM PAGE TEXT
# ==============================================================================
MAX_CHARS = 1000
MIN_WORDS = 100


def _collect_text():
    print(f"  Enter your text (max {MAX_CHARS} characters, min {MIN_WORDS} words).")
    print(f"  {DIM}Finish by typing a line containing only: END{RESET}")
    lines = []
    while True:
        try:
            line = safe_input("  > ")
        except KeyboardInterrupt:
            raise
        if line.strip().upper() == "END":
            break
        lines.append(line)
        current = "\n".join(lines)
        if len(current) > MAX_CHARS:
            err(f"Text is already {len(current)} characters "
                f"(limit {MAX_CHARS}). Stopping input.")
            break
    return "\n".join(lines).strip()


def _validate_text(text):
    problems = []
    if len(text) > MAX_CHARS:
        problems.append(f"too long ({len(text)}/{MAX_CHARS} chars)")
    words = len(text.split())
    if words < MIN_WORDS:
        problems.append(f"not enough words ({words}/{MIN_WORDS})")
    return problems


def _preview_wrapped_text():
    """Show how the text will be wrapped in the PDF (terminal approximation)."""
    custom = STATE["custom"]
    page_w, page_h = PAGE_SIZES.get(custom["page_size"].upper(), A4)
    if custom["orientation"] == "landscape":
        page_w, page_h = page_h, page_w

    margin = custom["text_width_margin"]
    max_width = page_w - 2 * margin
    font = custom["font_name"]
    size = custom["font_size"]

    lines = []
    for paragraph in STATE["custom_text"].split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        if HAS_REPORTLAB and simpleSplit is not None:
            wrapped = simpleSplit(paragraph, font, size, max_width)
        else:                                              # pragma: no cover
            approx = max(20, int(max_width / (size * 0.5)))
            wrapped = re.findall(r".{1,%d}" % approx, paragraph)
        lines.extend(wrapped if wrapped else [""])

    print(f"\n{BOLD}  Preview (wrapped to {len(lines)} lines, "
          f"font {font} {size}pt, {custom['align']} aligned){RESET}")
    print(f"{DIM}  " + "-" * 58 + RESET)
    for line in lines[:60]:
        if custom["align"] == "center":
            print("  " + line.center(56))
        elif custom["align"] == "right":
            print("  " + line.rjust(56))
        else:
            print("  " + line)
    if len(lines) > 60:
        print(f"{DIM}  ... ({len(lines) - 60} more lines){RESET}")
    print(f"{DIM}  " + "-" * 58 + RESET)
    print(f"  Vertical placement : {custom['text_position']}")
    print(f"  Pages              : "
          f"{'all pages' if custom['text_all_pages'] else 'first page only'}")


def do_custom_text():
    print(header("ADD CUSTOM PAGE TEXT"))
    text = _collect_text()

    if not text:
        warn("No text entered - nothing was changed.")
        return

    problems = _validate_text(text)
    if problems:
        err("The text does not meet the requirements:")
        for problem in problems:
            print(f"    {RED}- {problem}{RESET}")
        log(f"Custom text rejected: {problems}", "ERROR")
        if not confirm("Use it anyway?", default=False):
            return

    STATE["custom_text"] = text
    words = len(text.split())
    ok(f"Custom text stored ({len(text)} chars, {words} words).")

    if confirm("Adjust font / alignment / position now?", default=True):
        _text_appearance_menu()

    if confirm("Show a preview now?", default=True):
        _preview_wrapped_text()


def _text_appearance_menu():
    custom = STATE["custom"]
    while True:
        print(f"\n{BOLD}  TEXT APPEARANCE{RESET}")
        print(f"   1. Font family        [{custom['font_name']}]")
        print(f"   2. Font size          [{custom['font_size']} pt]")
        print(f"   3. Alignment          [{custom['align']}]")
        print(f"   4. Vertical position  [{custom['text_position']}]")
        print(f"   5. Left/right margin  [{custom['text_width_margin']} pt]")
        print(f"   6. Draw on            "
              f"[{'all pages' if custom['text_all_pages'] else 'first page'}]")
        print( "   0. Back")
        choice = safe_input("  Choice: ").strip()

        if choice == "1":
            print("  Fonts:")
            for key, value in FONT_CHOICES.items():
                print(f"    {key}. {value}")
            pick = safe_input("  Font number: ").strip()
            if pick in FONT_CHOICES:
                custom["font_name"] = FONT_CHOICES[pick]
        elif choice == "2":
            custom["font_size"] = ask_int("Font size (pt)", custom["font_size"], 6, 72)
        elif choice == "3":
            custom["align"] = ask_choice("Alignment",
                                         ["left", "center", "right"],
                                         custom["align"])
        elif choice == "4":
            custom["text_position"] = ask_choice("Vertical position",
                                                 ["top", "center", "bottom"],
                                                 custom["text_position"])
        elif choice == "5":
            custom["text_width_margin"] = ask_int("Margin (pt)",
                                                  custom["text_width_margin"], 10, 200)
        elif choice == "6":
            custom["text_all_pages"] = ask_choice(
                "Draw text on", ["all pages", "first page"],
                "all pages" if custom["text_all_pages"] else "first page"
            ) == "all pages"
        elif choice == "0":
            return
        else:
            warn("Invalid choice.")


# ==============================================================================
# 6. CUSTOMIZE PDF APPEARANCE
# ==============================================================================
def do_customize():
    custom = STATE["custom"]
    while True:
        print(header("CUSTOMIZE PDF APPEARANCE"))
        print(f"   1. Title              [{custom['title'] or '(empty)'}]")
        print(f"   2. Author             [{custom['author'] or '(empty)'}]")
        print(f"   3. Subject            [{custom['subject'] or '(empty)'}]")
        print(f"   4. Keywords           [{custom['keywords'] or '(empty)'}]")
        print(f"   5. Page numbering     [{'on' if custom['page_numbers'] else 'off'}]")
        print(f"   6. Header text        [{custom['header_text'] or '(empty)'}]")
        print(f"   7. Footer text        [{custom['footer_text'] or '(empty)'}]")
        print(f"   8. Watermark text     [{custom['watermark'] or '(empty)'}]")
        print(f"   9. Background colour  [{custom['background']}]")
        print(f"  10. Text position      [{custom['text_position']}]")
        print(f"  11. Font               [{custom['font_name']} {custom['font_size']}pt]")
        print(f"  12. Text alignment     [{custom['align']}]")
        print(f"  13. Page size          [{custom['page_size']}]")
        print(f"  14. Orientation        [{custom['orientation']}]")
        print(f"  15. Show all settings")
        print( "   0. Back")
        choice = safe_input("  Choice: ").strip()

        if choice == "1":
            custom["title"] = safe_input("  Title: ").strip()
        elif choice == "2":
            custom["author"] = safe_input("  Author: ").strip()
        elif choice == "3":
            custom["subject"] = safe_input("  Subject: ").strip()
        elif choice == "4":
            custom["keywords"] = safe_input("  Keywords (comma separated): ").strip()
        elif choice == "5":
            custom["page_numbers"] = confirm("Enable page numbering?",
                                             custom["page_numbers"])
        elif choice == "6":
            custom["header_text"] = safe_input("  Header text: ").strip()
        elif choice == "7":
            custom["footer_text"] = safe_input("  Footer text: ").strip()
        elif choice == "8":
            custom["watermark"] = safe_input("  Watermark text: ").strip()
        elif choice == "9":
            value = safe_input("  Background colour (#RRGGBB, empty = white): ").strip()
            if not value:
                custom["background"] = "#FFFFFF"
            elif is_valid_hex_color(value):
                custom["background"] = value.upper()
            else:
                err("Invalid colour format. Use #RRGGBB.")
        elif choice == "10":
            custom["text_position"] = ask_choice("Text position",
                                                 ["top", "center", "bottom"],
                                                 custom["text_position"])
        elif choice == "11":
            print("  Fonts:")
            for key, value in FONT_CHOICES.items():
                print(f"    {key}. {value}")
            pick = safe_input("  Font number: ").strip()
            if pick in FONT_CHOICES:
                custom["font_name"] = FONT_CHOICES[pick]
            custom["font_size"] = ask_int("Font size (pt)", custom["font_size"], 6, 72)
        elif choice == "12":
            custom["align"] = ask_choice("Alignment",
                                         ["left", "center", "right"], custom["align"])
        elif choice == "13":
            custom["page_size"] = ask_choice("Page size",
                                             ["A4", "LETTER", "LEGAL"],
                                             custom["page_size"])
        elif choice == "14":
            custom["orientation"] = ask_choice("Orientation",
                                               ["portrait", "landscape"],
                                               custom["orientation"])
        elif choice == "15":
            _print_settings_summary()
        elif choice == "0":
            log("Customization closed")
            return
        else:
            warn("Invalid choice.")


def _print_settings_summary():
    custom = STATE["custom"]
    print(f"\n{BOLD}  CURRENT SETTINGS{RESET}")
    for key in ("title", "author", "subject", "keywords", "header_text",
                "footer_text", "watermark", "background", "text_position",
                "font_name", "font_size", "align", "page_size", "orientation",
                "page_numbers", "text_all_pages", "text_width_margin"):
        print(f"    {key:<20}: {custom[key]}")
    print(f"    {'text_block_length':<20}: {len(STATE['custom_text'])} chars")


# ==============================================================================
# 7. IMPORT BATCH CODE
# ==============================================================================
def do_import_batch():
    print(header("IMPORT BATCH CODE FROM TXT"))
    info("Imported batch code is treated as INERT TEXT ONLY.")
    info("It is never executed, parsed as a script, or embedded as active code.")

    raw = safe_input("  Batch TXT file path: ")
    path = clean_path(raw)
    if not path or not os.path.isfile(path):
        err("File not found.")
        return
    if not os.access(path, os.R_OK):
        err("Permission denied.")
        return

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception as exc:
        err(f"Cannot read the file: {exc}")
        log(traceback.format_exc(), "ERROR")
        return

    if not content.strip():
        warn("The file is empty.")
        return

    STATE["batch_code"] = content
    log(f"Batch code imported (inert): {path} ({len(content)} chars)")

    ok(f"Batch code imported: {len(content)} characters, "
       f"{len(content.splitlines())} lines.")
    print(f"\n{DIM}--- imported batch code (first 1500 chars) ---{RESET}")
    print(content[:1500])
    if len(content) > 1500:
        print(f"{DIM}... ({len(content) - 1500} more characters){RESET}")
    print(f"{DIM}--- end ---{RESET}")

    if confirm("Attach this batch code as an inert TXT attachment?", default=True):
        _store_attachment(os.path.basename(path) or "batch_code.txt",
                          content.encode("utf-8", errors="replace"))
        ok("Stored as an inert attachment.")


# ==============================================================================
# 8. IMPORT JAVASCRIPT SOURCE
# ==============================================================================
def do_import_js():
    print(header("IMPORT JAVASCRIPT SOURCE FROM TXT"))
    info("JavaScript is stored as INERT TEXT ONLY - never executed.")
    info("It is never inserted as PDF JavaScript / OpenAction / Launch action.")

    raw = safe_input("  JavaScript TXT file path: ")
    path = clean_path(raw)
    if not path or not os.path.isfile(path):
        err("File not found.")
        return
    if not os.access(path, os.R_OK):
        err("Permission denied.")
        return

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception as exc:
        err(f"Cannot read the file: {exc}")
        log(traceback.format_exc(), "ERROR")
        return

    if not content.strip():
        warn("The file is empty.")
        return

    STATE["js_source"] = content
    log(f"JavaScript source imported (inert): {path} ({len(content)} chars)")

    ok(f"JavaScript source imported: {len(content)} characters, "
       f"{len(content.splitlines())} lines.")
    print(f"\n{DIM}--- imported JavaScript (first 1500 chars) ---{RESET}")
    print(content[:1500])
    if len(content) > 1500:
        print(f"{DIM}... ({len(content) - 1500} more characters){RESET}")
    print(f"{DIM}--- end ---{RESET}")

    if confirm("Attach this JavaScript as an inert TXT attachment?", default=True):
        name = os.path.basename(path) or "javascript_source.txt"
        if not name.lower().endswith(".txt"):
            name += ".txt"
        _store_attachment(name, content.encode("utf-8", errors="replace"))
        ok("Stored as an inert attachment.")


# ==============================================================================
# 9. ATTACHMENTS
# ==============================================================================
def _store_attachment(name, data, source_path=None):
    """Register an attachment in memory (and copy it into attachments/)."""
    entry = {
        "name": name,
        "path": source_path,
        "data": data,
        "size": len(data),
    }
    STATE["attachments"].append(entry)
    try:
        dest = os.path.join(DIRS["attachments"], name)
        base, ext = os.path.splitext(dest)
        counter = 1
        while os.path.exists(dest):
            dest = f"{base}_{counter}{ext}"
            counter += 1
        with open(dest, "wb") as fh:
            fh.write(data)
        entry["stored_copy"] = dest
    except Exception as exc:
        log(f"Could not copy attachment to disk: {exc}", "ERROR")
    log(f"Attachment added: {name} ({len(data)} bytes)")


def do_attachments():
    while True:
        print(header("ATTACHMENTS (INERT DOWNLOADABLES)"))
        print(f"   1. Add attachment from file   ({len(STATE['attachments'])} loaded)")
        print( "   2. List attachments")
        print( "   3. Extract an attachment")
        print( "   4. Remove an attachment")
        print( "   0. Back")
        choice = safe_input("  Choice: ").strip()

        if choice == "1":
            _attach_file()
        elif choice == "2":
            _list_attachments()
        elif choice == "3":
            _extract_attachment()
        elif choice == "4":
            _remove_attachment()
        elif choice == "0":
            return
        else:
            warn("Invalid choice.")


def _attach_file():
    raw = safe_input("  File path to attach: ")
    path = clean_path(raw)
    if not path or not os.path.isfile(path):
        err("File not found.")
        return
    ext = os.path.splitext(path)[1].lower()
    if ext not in SAFE_ATTACHMENT_EXT:
        warn(f"Extension '{ext}' is not in the safe list.")
        if not confirm("Attach anyway (as inert data)?", default=False):
            return
    if not os.access(path, os.R_OK):
        err("Permission denied.")
        return
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except Exception as exc:
        err(f"Cannot read the file: {exc}")
        return
    if not data:
        warn("The file is empty.")
        return
    _store_attachment(os.path.basename(path), data, source_path=path)
    ok(f"Attached '{os.path.basename(path)}' ({human_size(len(data))}).")


def _list_attachments():
    if not STATE["attachments"]:
        warn("No attachments loaded.")
        return
    print(f"\n{BOLD}  {'#':<3} {'Name':<38} {'Size':>10}{RESET}")
    print(f"{DIM}  " + "-" * 55 + RESET)
    for idx, entry in enumerate(STATE["attachments"], 1):
        name = entry["name"]
        if len(name) > 36:
            name = name[:33] + "..."
        print(f"  {idx:<3} {name:<38} {human_size(entry['size']):>10}")
    total = sum(e["size"] for e in STATE["attachments"])
    print(f"{DIM}  " + "-" * 55 + RESET)
    print(f"  Total: {human_size(total)}")


def _extract_attachment():
    if not STATE["attachments"]:
        warn("No attachments loaded.")
        return
    _list_attachments()
    idx = ask_int("Attachment number to extract", 1, 1, len(STATE["attachments"]))
    entry = STATE["attachments"][idx - 1]
    out_dir = safe_input(f"  Output directory [{DIRS['output']}]: ").strip()
    out_dir = clean_path(out_dir) or DIRS["output"]
    try:
        os.makedirs(out_dir, exist_ok=True)
        dest = os.path.join(out_dir, entry["name"])
        with open(dest, "wb") as fh:
            fh.write(entry["data"])
        ok(f"Extracted to: {dest}")
        log(f"Attachment extracted: {dest}")
    except Exception as exc:
        err(f"Extraction failed: {exc}")


def _remove_attachment():
    if not STATE["attachments"]:
        warn("No attachments loaded.")
        return
    _list_attachments()
    idx = ask_int("Attachment number to remove", 1, 1, len(STATE["attachments"]))
    removed = STATE["attachments"].pop(idx - 1)
    ok(f"Removed '{removed['name']}'.")
    log(f"Attachment removed: {removed['name']}")


# ==============================================================================
# 10. PDF INFORMATION AND METADATA
# ==============================================================================
def do_pdf_info():
    print(header("PDF INFORMATION AND METADATA"))
    path = STATE["source_pdf"]
    if not path or not os.path.isfile(path):
        warn("No PDF selected.")
        return
    if not HAS_PYPDF:
        err("pypdf is required. Install: pip install pypdf")
        return

    desc = describe_pdf(path)
    if desc is None:
        err("Cannot read that PDF.")
        return
    print_pdf_description(desc)

    print(f"\n{BOLD}  PENDING CUSTOMIZATION{RESET}")
    custom = STATE["custom"]
    for key in ("title", "author", "subject", "keywords"):
        print(f"    {key:<10}: {custom[key] or '(empty)'}")
    print(f"    text block: {len(STATE['custom_text'])} chars")
    print(f"    attachments: {len(STATE['attachments'])}")
    print(f"    batch code: {'loaded' if STATE['batch_code'] else 'none'}")
    print(f"    javascript: {'loaded' if STATE['js_source'] else 'none'}")

    if STATE["original_pdf"]:
        print(f"\n    {BOLD}Original (preserved){RESET}: {STATE['original_pdf']}")


# ==============================================================================
# 11. PDF VALIDATION
# ==============================================================================
def validate_pdf(path):
    """Run a series of checks. Returns a list of (label, ok, detail)."""
    results = []

    if not path:
        return [("File selected", False, "no file")]

    exists = os.path.isfile(path)
    results.append(("File exists", exists, path if exists else "not found"))
    if not exists:
        return results

    try:
        size = os.path.getsize(path)
    except Exception:
        size = 0
    results.append(("File size", size > 0, f"{human_size(size)} ({size} bytes)"))

    readable = os.access(path, os.R_OK)
    results.append(("Read permission", readable, "readable" if readable else "denied"))

    try:
        with open(path, "rb") as fh:
            magic = fh.read(5)
        results.append(("PDF header", magic.startswith(b"%PDF"),
                        magic.decode("latin-1", "replace")))
    except Exception as exc:
        results.append(("PDF header", False, str(exc)))
        return results

    if not HAS_PYPDF:
        results.append(("PDF parser", False, "pypdf not installed"))
        return results

    try:
        reader = PdfReader(path)
        pages = len(reader.pages)
        results.append(("Page count", pages > 0, f"{pages} pages"))
    except Exception as exc:
        results.append(("Readable / parseable", False, str(exc)))
        return results

    try:
        meta = reader.metadata
        results.append(("Metadata", True,
                        f"{len(dict(meta)) if meta else 0} entries"))
    except Exception as exc:
        results.append(("Metadata", False, str(exc)))

    try:
        if pages:
            _ = reader.pages[0].mediabox
            results.append(("Page geometry", True,
                            f"{float(_.width):.0f} x {float(_.height):.0f} pt"))
        else:
            results.append(("Page geometry", False, "no pages"))
    except Exception as exc:
        results.append(("Page geometry", False, str(exc)))

    try:
        attachments = list_pdf_attachments(path)
        results.append(("Attachment integrity", True,
                        f"{len(attachments)} attachment(s)"))
    except Exception as exc:
        results.append(("Attachment integrity", False, str(exc)))

    return results


def do_validate():
    print(header("PDF VALIDATION"))
    path = STATE["source_pdf"]
    if not path:
        warn("No PDF selected.")
        return

    results = validate_pdf(path)
    print(f"  {BOLD}Target:{RESET} {path}\n")
    failures = 0
    for label, passed, detail in results:
        tag = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
        print(f"  {tag} {label:<24} {DIM}{detail}{RESET}")
        if not passed:
            failures += 1

    print()
    if failures == 0:
        ok("All checks passed. The PDF looks healthy.")
    else:
        err(f"{failures} check(s) failed.")
    log(f"Validation of {path}: {failures} failure(s)")


# ==============================================================================
# 12. EXPORT
# ==============================================================================
def _has_background(colour):
    if not colour:
        return False
    return colour.strip().lower() not in ("#ffffff", "#fff", "white", "none")


def _draw_background_rect(canv, width, height, colour):
    try:
        canv.setFillColor(HexColor(colour))
        canv.rect(0, 0, width, height, stroke=0, fill=1)
    except Exception as exc:
        log(f"Background draw failed: {exc}", "ERROR")


def _draw_decorations(canv, index, total, width, height):
    """Watermark, header, footer, page numbers and the custom text block."""
    custom = STATE["custom"]

    # ---- watermark -----------------------------------------------------------
    if custom["watermark"]:
        try:
            canv.saveState()
            try:
                canv.setFillColor(HexColor("#B0B0B0"))
            except Exception:
                canv.setFillColorRGB(0.69, 0.69, 0.69)
            try:
                canv.setFillAlpha(0.18)
            except Exception:
                pass
            canv.setFont("Helvetica-Bold", 60)
            canv.translate(width / 2.0, height / 2.0)
            canv.rotate(45)
            canv.drawCentredString(0, 0, custom["watermark"])
            canv.restoreState()
        except Exception as exc:
            log(f"Watermark error: {exc}", "ERROR")
            try:
                canv.restoreState()
            except Exception:
                pass

    # ---- header --------------------------------------------------------------
    if custom["header_text"]:
        try:
            canv.setFont("Helvetica", 9)
            canv.setFillColor(HexColor("#444444"))
            canv.drawCentredString(width / 2.0, height - 30, custom["header_text"])
        except Exception as exc:
            log(f"Header error: {exc}", "ERROR")

    # ---- footer --------------------------------------------------------------
    if custom["footer_text"]:
        try:
            canv.setFont("Helvetica", 9)
            canv.setFillColor(HexColor("#444444"))
            canv.drawCentredString(width / 2.0, 30, custom["footer_text"])
        except Exception as exc:
            log(f"Footer error: {exc}", "ERROR")

    # ---- page numbers --------------------------------------------------------
    if custom["page_numbers"]:
        try:
            canv.setFont("Helvetica", 9)
            canv.setFillColor(HexColor("#444444"))
            canv.drawCentredString(width / 2.0, 18,
                                   f"Page {index + 1} of {total}")
        except Exception as exc:
            log(f"Page number error: {exc}", "ERROR")

    # ---- custom text block ---------------------------------------------------
    if STATE["custom_text"] and (custom["text_all_pages"] or index == 0):
        _draw_custom_text(canv, width, height)


def _draw_custom_text(canv, width, height):
    custom = STATE["custom"]
    font = custom["font_name"]
    size = custom["font_size"]
    margin = custom["text_width_margin"]
    max_width = width - 2 * margin
    if max_width <= 20:
        max_width = width - 40
        margin = 20

    lines = []
    for paragraph in STATE["custom_text"].split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        if HAS_REPORTLAB and simpleSplit is not None:
            wrapped = simpleSplit(paragraph, font, size, max_width)
        else:                                              # pragma: no cover
            approx = max(20, int(max_width / (size * 0.5)))
            wrapped = re.findall(r".{1,%d}" % approx, paragraph)
        lines.extend(wrapped if wrapped else [""])

    leading = size * 1.35
    block_height = len(lines) * leading

    position = custom["text_position"]
    if position == "top":
        top_y = height - margin
    elif position == "bottom":
        top_y = 60 + block_height
    else:  # center
        top_y = (height + block_height) / 2.0

    try:
        canv.setFont(font, size)
        canv.setFillColor(HexColor("#000000"))
    except Exception:
        canv.setFont("Helvetica", size)

    y = top_y - size
    for line in lines:
        if y < 20:            # never spill off the page
            break
        try:
            if custom["align"] == "center":
                canv.drawCentredString(width / 2.0, y, line)
            elif custom["align"] == "right":
                canv.drawRightString(width - margin, y, line)
            else:
                canv.drawString(margin, y, line)
        except Exception as exc:
            log(f"Text draw error: {exc}", "ERROR")
            break
        y -= leading


def _render_overlay(index, total, width, height):
    """Create a one-page PDF overlay with decorations, return its PageObject."""
    buffer = io.BytesIO()
    canv = rl_canvas.Canvas(buffer, pagesize=(width, height))
    _draw_decorations(canv, index, total, width, height)
    canv.showPage()
    canv.save()
    buffer.seek(0)
    overlay_reader = PdfReader(buffer)
    return overlay_reader.pages[0]


def _render_background(width, height, colour):
    """Create a one-page PDF filled with the background colour."""
    buffer = io.BytesIO()
    canv = rl_canvas.Canvas(buffer, pagesize=(width, height))
    _draw_background_rect(canv, width, height, colour)
    canv.showPage()
    canv.save()
    buffer.seek(0)
    bg_reader = PdfReader(buffer)
    return bg_reader.pages[0]


def _set_writer_metadata(writer, custom):
    meta = {}
    if custom["title"]:
        meta["/Title"] = custom["title"]
    if custom["author"]:
        meta["/Author"] = custom["author"]
    if custom["subject"]:
        meta["/Subject"] = custom["subject"]
    if custom["keywords"]:
        meta["/Keywords"] = custom["keywords"]
    meta["/Producer"] = "PDF BUILDER PRO v1.0"
    meta["/Creator"] = "PDF BUILDER PRO"
    if not meta:
        return
    try:
        if hasattr(writer, "add_metadata"):
            writer.add_metadata(meta)
        elif hasattr(writer, "addMetadata"):            # pragma: no cover
            writer.addMetadata(meta)
    except Exception as exc:
        log(f"Metadata write failed: {exc}", "ERROR")


def _attach_to_writer(writer, name, data):
    try:
        if hasattr(writer, "add_attachment"):
            writer.add_attachment(name, data)
            return True
        if hasattr(writer, "addAttachment"):            # pragma: no cover
            writer.addAttachment(name, data)
            return True
        return False
    except Exception as exc:
        log(f"Attachment embedding failed for {name}: {exc}", "ERROR")
        return False


def build_final_pdf(out_path, blank_pages=1):
    """Build the final PDF and return (ok, message)."""
    if not (HAS_PYPDF and HAS_REPORTLAB):
        return False, "reportlab and pypdf are required."

    custom = STATE["custom"]
    page_w, page_h = PAGE_SIZES.get(custom["page_size"].upper(), A4)
    if custom["orientation"] == "landscape":
        page_w, page_h = page_h, page_w

    writer = PdfWriter()

    source = STATE["source_pdf"]
    if source and os.path.isfile(source):
        reader = PdfReader(source)
        total = len(reader.pages)
        if total == 0:
            return False, "The source PDF contains no pages."

        for index in range(total):
            page = reader.pages[index]
            try:
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)
            except Exception:
                width, height = page_w, page_h

            overlay = _render_overlay(index, total, width, height)

            if _has_background(custom["background"]):
                background = _render_background(width, height,
                                                custom["background"])
                background.merge_page(page)      # source drawn over background
                base = background
            else:
                base = page

            base.merge_page(overlay)             # decorations on top
            writer.add_page(base)
    else:
        total = max(1, blank_pages)
        buffer = io.BytesIO()
        canv = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))
        for index in range(total):
            if _has_background(custom["background"]):
                _draw_background_rect(canv, page_w, page_h, custom["background"])
            _draw_decorations(canv, index, total, page_w, page_h)
            canv.showPage()
        canv.save()
        buffer.seek(0)
        base_reader = PdfReader(buffer)
        for page in base_reader.pages:
            writer.add_page(page)

    _set_writer_metadata(writer, custom)

    embedded = 0
    for entry in STATE["attachments"]:
        if _attach_to_writer(writer, entry["name"], entry["data"]):
            embedded += 1

    try:
        with open(out_path, "wb") as fh:
            writer.write(fh)
    except PermissionError:
        return False, "Permission denied while writing the output file."
    except Exception as exc:
        log(traceback.format_exc(), "ERROR")
        return False, f"Write failed: {exc}"

    return True, f"{embedded} attachment(s) embedded."


def do_export():
    print(header("EXPORT FINAL PDF"))
    if not (HAS_PYPDF and HAS_REPORTLAB):
        err("Export requires reportlab and pypdf.")
        err("Install with:  pip install reportlab pypdf")
        return

    if not STATE["source_pdf"]:
        warn("No source PDF selected - a fresh document will be generated.")
    if STATE["original_pdf"]:
        info(f"Original preserved (never modified): {STATE['original_pdf']}")

    # ---- output directory ----------------------------------------------------
    raw_dir = safe_input(f"  Output directory [{STATE['output_dir']}]: ").strip()
    out_dir = clean_path(raw_dir) or STATE["output_dir"]
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as exc:
        err(f"Cannot create the output directory: {exc}")
        return
    if not os.access(out_dir, os.W_OK):
        err("The output directory is not writable.")
        return
    STATE["output_dir"] = out_dir

    # ---- output filename -----------------------------------------------------
    raw_name = safe_input(f"  Output filename [{STATE['output_name']}]: ").strip()
    name = raw_name or STATE["output_name"]
    name = os.path.basename(name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    STATE["output_name"] = name
    out_path = os.path.join(out_dir, name)

    if os.path.exists(out_path):
        warn(f"'{name}' already exists in that folder.")
        if not confirm("Overwrite it?", default=False):
            return

    # ---- pages for a brand-new document --------------------------------------
    blank_pages = 1
    if not STATE["source_pdf"]:
        blank_pages = ask_int("Pages for the new document", 1, 1, 500)

    # ---- build ---------------------------------------------------------------
    info("Building the final PDF...")
    success, message = build_final_pdf(out_path, blank_pages=blank_pages)

    if not success:
        err(message)
        log(f"Export failed: {message}", "ERROR")
        return

    # ---- verify --------------------------------------------------------------
    if not os.path.isfile(out_path):
        err("The output file was not created.")
        return
    size = os.path.getsize(out_path)
    if size <= 0:
        err("The output file is empty.")
        return

    verified = False
    try:
        reader = PdfReader(out_path)
        pages = len(reader.pages)
        verified = pages > 0
    except Exception as exc:
        log(f"Post-export verification failed: {exc}", "ERROR")
        pages = 0

    print()
    ok("Export completed.")
    print(f"  {BOLD}File      :{RESET} {out_path}")
    print(f"  {BOLD}Size      :{RESET} {human_size(size)}")
    print(f"  {BOLD}Pages     :{RESET} {pages}")
    print(f"  {BOLD}Details   :{RESET} {message}")
    if verified:
        ok("Verification passed: the file opens and contains pages.")
    else:
        warn("Verification could not confirm the output - please check manually.")

    log(f"Export OK: {out_path} ({size} bytes, {pages} pages)")


# ==============================================================================
# 13. VIEW LOGS
# ==============================================================================
def do_view_logs():
    print(header("LOGS"))
    if not os.path.isfile(LOG_FILE):
        warn("No log file yet.")
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except Exception as exc:
        err(f"Cannot read the log file: {exc}")
        return

    tail = lines[-60:]
    for line in tail:
        stripped = line.rstrip()
        if "[ERROR]" in stripped:
            print(f"  {RED}{stripped}{RESET}")
        elif "[WARNING]" in stripped:
            print(f"  {YELLOW}{stripped}{RESET}")
        else:
            print(f"  {stripped}")

    print(f"\n  {DIM}{len(lines)} total entries | {LOG_FILE}{RESET}")
    if confirm("Clear the log file?", default=False):
        try:
            open(LOG_FILE, "w", encoding="utf-8").close()
            ok("Log cleared.")
        except Exception as exc:
            err(f"Cannot clear the log: {exc}")


# ==============================================================================
# 14. SETTINGS
# ==============================================================================
def do_settings():
    while True:
        print(header("SETTINGS"))
        custom = STATE["custom"]
        print(f"   1. Default output directory  [{STATE['output_dir']}]")
        print(f"   2. Default output filename   [{STATE['output_name']}]")
        print(f"   3. Text block margin         [{custom['text_width_margin']} pt]")
        print(f"   4. Draw text on              "
              f"[{'all pages' if custom['text_all_pages'] else 'first page'}]")
        print(f"   5. Show folder layout")
        print(f"   6. Clean temporary files")
        print(f"   7. Reset all customization to defaults")
        print( "   0. Back")
        choice = safe_input("  Choice: ").strip()

        if choice == "1":
            raw = safe_input(f"  New output directory [{STATE['output_dir']}]: ").strip()
            path = clean_path(raw)
            if not path:
                continue
            try:
                os.makedirs(path, exist_ok=True)
                STATE["output_dir"] = path
                ok("Output directory updated.")
            except Exception as exc:
                err(f"Cannot use that directory: {exc}")
        elif choice == "2":
            raw = safe_input(f"  New filename [{STATE['output_name']}]: ").strip()
            if raw:
                name = os.path.basename(raw)
                if not name.lower().endswith(".pdf"):
                    name += ".pdf"
                STATE["output_name"] = name
                ok("Filename updated.")
        elif choice == "3":
            custom["text_width_margin"] = ask_int("Text block margin (pt)",
                                                  custom["text_width_margin"], 10, 200)
        elif choice == "4":
            custom["text_all_pages"] = ask_choice(
                "Draw text on", ["all pages", "first page"],
                "all pages" if custom["text_all_pages"] else "first page"
            ) == "all pages"
        elif choice == "5":
            print(f"\n{BOLD}  Working folders{RESET}")
            for key, path in DIRS.items():
                print(f"    {key:<12}: {path}")
            print(f"    {'log file':<12}: {LOG_FILE}")
        elif choice == "6":
            cleanup_temp()
            ok("Temporary files cleaned.")
        elif choice == "7":
            if confirm("Reset all customization to defaults?", default=False):
                STATE["custom"] = {
                    "title": "", "author": "", "subject": "", "keywords": "",
                    "page_numbers": True, "header_text": "", "footer_text": "",
                    "watermark": "", "background": "#FFFFFF",
                    "text_position": "center", "font_name": "Helvetica",
                    "font_size": 12, "align": "left", "page_size": "A4",
                    "orientation": "portrait", "text_width_margin": 50,
                    "text_all_pages": True,
                }
                ok("Customization reset.")
        elif choice == "0":
            return
        else:
            warn("Invalid choice.")


# ==============================================================================
# MENU DISPATCH
# ==============================================================================
MENU_ACTIONS = {
    "1": do_create_new_pdf,
    "2": do_select_pdf,
    "3": do_preview_pdf,
    "4": do_enter_original_path,
    "5": do_custom_text,
    "6": do_customize,
    "7": do_import_batch,
    "8": do_import_js,
    "9": do_attachments,
    "10": do_pdf_info,
    "11": do_validate,
    "12": do_export,
    "13": do_view_logs,
    "14": do_settings,
}


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    setup_dirs()
    log("=" * 60)
    log("PDF BUILDER PRO started")

    try:
        print_banner()
        check_dependencies()

        while True:
            print_menu()
            try:
                choice = safe_input(f"  {BOLD}Select an option:{RESET} ").strip()
            except KeyboardInterrupt:
                raise

            if choice == "0":
                break

            action = MENU_ACTIONS.get(choice)
            if action is None:
                warn("Invalid option. Choose a number from the menu.")
                continue

            try:
                action()
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                err(f"Unexpected error: {exc}")
                log(traceback.format_exc(), "ERROR")
                print(f"{DIM}  Details were written to the log file.{RESET}")

            pause()

        print(f"\n{CYAN}  Shutting down...{RESET}")
        cleanup_temp()
        log("PDF BUILDER PRO closed normally")
        print(f"{GREEN}  Goodbye!{RESET}\n")
        return 0

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}  Interrupted by user (CTRL+C).{RESET}")
        cleanup_temp()
        log("Interrupted by user (CTRL+C)", "WARNING")
        print(f"{GREEN}  Temporary files cleaned. Goodbye!{RESET}\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())