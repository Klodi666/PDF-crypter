#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Security-Awareness PDF Generator
================================

A beginner-friendly Tkinter desktop app that writes a security-awareness
*simulation* PDF to a folder you choose.

Safety properties:
  * No JavaScript, macros, forms, embedded files or launch actions in the PDF.
  * The training URL is printed as PLAIN, NON-CLICKABLE TEXT.
  * Only https:// web-page URLs are accepted; executables/archives are rejected.
  * Nothing is fetched, opened or downloaded - ever.

Requires: Python 3.8+ and `reportlab`
    pip install reportlab
"""

from __future__ import annotations

import datetime as dt
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import unquote, urlsplit
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

APP_TITLE = "Security-Awareness PDF Generator"
MAX_URL_LENGTH = 512

# Extensions that look like downloadable / executable payloads.
BLOCKED_EXTENSIONS = {
    ".exe", ".msi", ".msp", ".msu", ".bat", ".cmd", ".com", ".scr", ".pif",
    ".cpl", ".dll", ".sys", ".drv", ".ocx", ".cab",
    ".js", ".jse", ".vbs", ".vbe", ".wsf", ".wsh", ".ps1", ".psm1", ".psd1",
    ".hta", ".jar", ".sh", ".bash", ".command", ".py", ".pyw", ".rb", ".pl",
    ".lnk", ".url", ".reg", ".scf", ".inf",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz",
    ".iso", ".img", ".vhd", ".vhdx",
    ".dmg", ".pkg", ".mpkg", ".deb", ".rpm", ".snap", ".appimage",
    ".apk", ".ipa", ".bin", ".run",
}

# Byte patterns that must never appear in the PDF we produce.
FORBIDDEN_PDF_MARKERS = (
    b"/JavaScript", b"/EmbeddedFile", b"/Launch", b"/RichMedia",
    b"/SubmitForm", b"/ImportData", b"/GoToR",
)

_HOST_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*$"
)

_WINDOWS_RESERVED = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #

def _extension_of(segment: str) -> str:
    segment = unquote(segment)
    segment = segment.split("#", 1)[0].split("?", 1)[0]
    if "." not in segment:
        return ""
    ext = segment.rsplit(".", 1)[-1].strip().lower()
    if not ext or len(ext) > 8 or not ext.isalnum():
        return ""
    return "." + ext


def _candidate_segments(parts) -> list:
    segments = []
    for piece in reversed([p for p in parts.path.split("/") if p]):
        segments.append(piece)
        break
    for pair in parts.query.split("&"):
        if not pair:
            continue
        if "=" in pair:
            segments.append(pair.split("=", 1)[1])
        else:
            segments.append(pair)
    return segments


def validate_url(raw: str):
    """Return (normalised_url, None) or (None, error_message)."""
    url = (raw or "").strip()
    if not url:
        return None, "Please enter the training landing-page URL."
    if len(url) > MAX_URL_LENGTH:
        return None, f"The URL is longer than {MAX_URL_LENGTH} characters."
    if re.search(r"\s", url):
        return None, "The URL must not contain spaces or line breaks."

    try:
        parts = urlsplit(url)
    except ValueError as exc:
        return None, f"That URL could not be parsed:\n{exc}"

    if parts.scheme.lower() != "https":
        return None, (
            "Only https:// URLs are accepted.\n\n"
            "http://, ftp://, file://, data:, javascript: and similar schemes "
            "are rejected."
        )
    if not parts.netloc:
        return None, "The URL is missing a host name, e.g. https://training.example.com/page"
    if "@" in parts.netloc:
        return None, "URLs that embed credentials (user@host) are not allowed."

    try:
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        return None, "The URL contains an invalid port number."

    if not host:
        return None, "The URL is missing a host name."
    if not _HOST_RE.match(host):
        return None, "The host name contains characters that are not allowed."
    if port is not None and not (1 <= port <= 65535):
        return None, "The port number must be between 1 and 65535."

    for segment in _candidate_segments(parts):
        ext = _extension_of(segment)
        if ext in BLOCKED_EXTENSIONS:
            return None, (
                f"The link ends in '{ext}', which looks like a downloadable or "
                "executable payload.\n\n"
                "This tool only accepts https:// web-page URLs that do not "
                "point at files."
            )

    return parts.geturl(), None


def validate_filename(raw: str) -> str:
    """Return a safe '<name>.pdf' string or raise ValueError."""
    name = (raw or "").strip()
    if not name:
        raise ValueError("Please enter a file name for the PDF.")

    stem = name[:-4] if name.lower().endswith(".pdf") else name
    stem = stem.strip().rstrip(". ")

    if not stem:
        raise ValueError("The file name needs at least one letter or digit before '.pdf'.")
    if any(ch in _INVALID_FILENAME_CHARS for ch in stem) or any(ord(ch) < 32 for ch in stem):
        raise ValueError('The file name contains characters that are not allowed:\n< > : " / \\ | ? *')
    if stem.upper() in _WINDOWS_RESERVED:
        raise ValueError(f"'{stem}' is a reserved name on Windows. Please choose another file name.")

    full = stem + ".pdf"
    if len(full) > 120:
        raise ValueError("The file name is too long. Please keep it under 120 characters.")
    return full


# --------------------------------------------------------------------------- #
# PDF creation
# --------------------------------------------------------------------------- #

def _draw_paragraph(pdf, text, style, x, y, width, gap=6.0, bullet_text=None):
    paragraph = Paragraph(text, style, bulletText=bullet_text)
    _, height = paragraph.wrapOn(pdf, width, 100 * cm)
    paragraph.drawOn(pdf, x, y - height)
    return y - height - gap


def build_pdf(out_path: str, url: str) -> None:
    """Write the simulation PDF (plain text + rectangles only)."""
    page_w, page_h = A4
    margin = 2 * cm
    content_w = page_w - 2 * margin

    pdf = canvas.Canvas(out_path, pagesize=A4)
    pdf.setTitle("Security-Awareness Simulation")
    pdf.setAuthor("Security-Awareness PDF Generator")
    pdf.setSubject("Security-awareness simulation - contains no active content")
    pdf.setCreator("Security-Awareness PDF Generator (ReportLab)")
    pdf.setKeywords(["security awareness", "simulation", "training"])

    body = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=10.5, leading=14.5,
        textColor=colors.HexColor("#1A1A1A"),
    )
    title_style = ParagraphStyle(
        "title", parent=body, fontName="Helvetica-Bold", fontSize=17, leading=21,
    )
    heading = ParagraphStyle(
        "heading", parent=body, fontName="Helvetica-Bold", fontSize=11.5, leading=15,
    )
    bullet = ParagraphStyle(
        "bullet", parent=body, leftIndent=16, bulletIndent=4, leading=14,
    )
    url_style = ParagraphStyle(
        "url", parent=body, fontName="Courier-Bold", fontSize=10.5, leading=14,
        textColor=colors.HexColor("#0B3D91"), wordWrap="CJK",
    )
    small = ParagraphStyle(
        "small", parent=body, fontSize=8.5, leading=11,
        textColor=colors.HexColor("#555555"),
    )

    y = page_h - margin

    # Red banner
    banner_h = 1.1 * cm
    pdf.setFillColor(colors.HexColor("#B00020"))
    pdf.rect(margin, y - banner_h, content_w, banner_h, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 11.5)
    pdf.drawCentredString(
        page_w / 2.0,
        y - banner_h + 0.34 * cm,
        "SECURITY-AWARENESS SIMULATION - NOT A REAL ATTACK",
    )
    y -= banner_h + 0.75 * cm

    y = _draw_paragraph(pdf, "Simulated landing-page notice", title_style,
                        margin, y, content_w, gap=8)

    y = _draw_paragraph(
        pdf,
        "This document was produced by a local security-awareness training tool. "
        "It is a harmless simulation that shows what a suspicious &quot;landing page&quot; "
        "link looks like inside a document, so that you can practise recognising and "
        "reporting this kind of message.",
        body, margin, y, content_w, gap=10,
    )

    y = _draw_paragraph(pdf, "Training landing page (plain text, not a link)",
                        heading, margin, y, content_w, gap=6)

    # URL box - plain text only
    url_paragraph = Paragraph(xml_escape(url), url_style)
    _, url_h = url_paragraph.wrapOn(pdf, content_w - 1.0 * cm, 100 * cm)
    box_h = url_h + 0.7 * cm

    pdf.setFillColor(colors.HexColor("#F4F6F8"))
    pdf.setStrokeColor(colors.HexColor("#9AA5B1"))
    pdf.setLineWidth(0.8)
    pdf.rect(margin, y - box_h, content_w, box_h, stroke=1, fill=1)
    url_paragraph.drawOn(pdf, margin + 0.5 * cm, y - box_h + 0.35 * cm)
    y -= box_h + 0.5 * cm

    y = _draw_paragraph(
        pdf,
        "The address above is plain text. It is not a hyperlink, it cannot be clicked, "
        "and this document never contacts it.",
        small, margin, y, content_w, gap=12,
    )

    y = _draw_paragraph(pdf, "What this document does not contain",
                        heading, margin, y, content_w, gap=5)
    for line in (
        "No JavaScript, macros, forms or other active content.",
        "No embedded files, attachments or launch actions.",
        "No automatic downloads, and no attempt to open any program.",
    ):
        y = _draw_paragraph(pdf, line, bullet, margin, y, content_w,
                            gap=2, bullet_text="\u2022")
    y -= 8

    y = _draw_paragraph(pdf, "If you receive a document like this",
                        heading, margin, y, content_w, gap=5)
    for line in (
        "Do not click unexpected links, even when the message looks urgent.",
        "Verify the sender and the destination address through a channel you already trust.",
        "Report the message to your IT or security team and then delete it.",
    ):
        y = _draw_paragraph(pdf, line, bullet, margin, y, content_w,
                            gap=2, bullet_text="\u2022")

    # Footer
    pdf.setFillColor(colors.HexColor("#666666"))
    pdf.setFont("Helvetica", 8)
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf.drawString(margin, margin * 0.55,
                   f"Generated locally on {stamp}. This PDF contains no active content.")
    pdf.drawRightString(page_w - margin, margin * 0.55, "Security-awareness simulation")

    pdf.showPage()
    pdf.save()


def scan_pdf_for_active_content(path: str) -> list:
    """Defence-in-depth: re-read the file and look for active-content markers."""
    with open(path, "rb") as handle:
        data = handle.read()
    return [m.decode("ascii") for m in FORBIDDEN_PDF_MARKERS if m in data]


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #

class GeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.resizable(False, False)

        self.var_filename = tk.StringVar(value="security-awareness-simulation.pdf")
        self.var_folder = tk.StringVar(value=os.path.expanduser("~"))
        self.var_url = tk.StringVar(value="https://training.example.com/awareness")
        self.var_status = tk.StringVar(value="Ready.")

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Create a security-awareness simulation PDF",
                  font=("TkDefaultFont", 13, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(
            frame,
            text=("The PDF is generated locally. The URL is printed as plain text and is "
                  "never opened, fetched or contacted."),
            foreground="#444444", wraplength=540, justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 12))

        ttk.Label(frame, text="PDF file name:").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.var_filename, width=48).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(frame, text="Save folder:").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.var_folder, width=48).grid(
            row=3, column=1, sticky="ew", padx=(8, 0), pady=4)
        ttk.Button(frame, text="Browse...", command=self.on_browse).grid(
            row=3, column=2, padx=(8, 0), pady=4)

        ttk.Label(frame, text="Training URL (https://):").grid(row=4, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.var_url, width=48).grid(
            row=4, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(
            frame,
            text=("Only https:// web-page addresses are accepted. Direct links to "
                  "executables, scripts or archives are rejected."),
            foreground="#444444", wraplength=540, justify="left",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(2, 8))

        ttk.Separator(frame, orient="horizontal").grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=6)

        self.btn_generate = ttk.Button(frame, text="Generate PDF", command=self.on_generate)
        self.btn_generate.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(2, 8))

        ttk.Label(frame, textvariable=self.var_status, foreground="#1B5E20",
                  wraplength=540, justify="left").grid(
            row=8, column=0, columnspan=3, sticky="w")

    def on_browse(self):
        start = self.var_folder.get().strip() or os.path.expanduser("~")
        folder = filedialog.askdirectory(
            title="Choose the folder where the PDF will be saved",
            initialdir=start,
            mustexist=True,
        )
        if folder:
            self.var_folder.set(folder)

    def on_generate(self):
        # 1. File name
        try:
            filename = validate_filename(self.var_filename.get())
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        # 2. Folder
        folder_raw = self.var_folder.get().strip()
        if not folder_raw:
            messagebox.showerror(APP_TITLE, "Please choose the folder where the PDF should be saved.")
            return
        folder = os.path.abspath(os.path.expanduser(folder_raw))
        if not os.path.isdir(folder):
            messagebox.showerror(APP_TITLE, f"The folder does not exist:\n{folder}")
            return
        if not os.access(folder, os.W_OK):
            messagebox.showerror(APP_TITLE, f"You do not have permission to write to:\n{folder}")
            return

        # 3. URL
        url, error = validate_url(self.var_url.get())
        if error:
            messagebox.showerror(APP_TITLE, error)
            return

        # 4. Resolve final path, keep it inside the chosen folder
        out_path = os.path.join(folder, filename)
        if os.path.dirname(os.path.realpath(out_path)) != os.path.realpath(folder):
            messagebox.showerror(APP_TITLE,
                                 "The resulting file path is outside the selected folder. Aborted.")
            return

        # 5. Overwrite confirmation
        if os.path.exists(out_path):
            if not messagebox.askyesno(
                APP_TITLE,
                f"'{filename}' already exists in that folder.\n\nReplace it?",
            ):
                self.var_status.set("Cancelled - the existing file was left untouched.")
                return

        # 6. Write the PDF
        try:
            build_pdf(out_path, url)
        except OSError as exc:
            self._remove_quietly(out_path)
            messagebox.showerror(APP_TITLE, f"Could not write the PDF:\n{exc}")
            return
        except Exception as exc:
            self._remove_quietly(out_path)
            messagebox.showerror(APP_TITLE, f"Unexpected error while creating the PDF:\n{exc}")
            return

        # 7. Defence-in-depth scan
        try:
            markers = scan_pdf_for_active_content(out_path)
        except OSError as exc:
            messagebox.showwarning(APP_TITLE,
                                   f"The PDF was written but could not be re-checked:\n{exc}")
            markers = []

        if markers:
            self._remove_quietly(out_path)
            messagebox.showerror(
                APP_TITLE,
                "The generated file failed a safety check and was deleted.\n\n"
                "Detected: " + ", ".join(markers),
            )
            self.var_status.set("Generation aborted: safety check failed.")
            return

        # 8. Success
        self.var_status.set(f"Saved: {out_path}")
        messagebox.showinfo(
            "PDF saved",
            "The security-awareness PDF was saved to:\n\n"
            f"{out_path}\n\n"
            "It contains no active content, no links and no downloads.",
        )

    @staticmethod
    def _remove_quietly(path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def main():
    app = GeneratorApp()
    app.mainloop()


if __name__ == "__main__":
    main()