#!/usr/bin/env python3
"""
[SEC-OPS] Security-Awareness PDF Generator (Hacker Terminal Edition)
=====================================================================
A fully debugged, feature-rich Tkinter desktop app designed with a tactical
terminal UI. It generates secure, static PDF awareness simulations.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    )
except ImportError:
    sys.stderr.write(
        "reportlab is required. Install it with:\n    pip install reportlab\n"
    )
    raise


# ======================================================================
# Constants & Terminal Themeing
# ======================================================================

APP_TITLE = "[SEC-OPS] // AWARENESS_PDF_GEN v3.0 [TACTICAL]"
HISTORY_FILE = os.path.join(os.path.expanduser("~"),
                            ".awareness_pdf_history.json")
MAX_HISTORY = 20

# Hacker Palette
BG_COLOR = "#0b0f0c"         # Deep tactical dark
PANEL_BG = "#121a14"         # Slightly lighter container shade
FG_COLOR = "#00ff66"         # Matrix phosphor green
TEXT_DIM = "#339944"         # Muted tactical green
ACCENT_GREEN = "#00ff66"     # Primary alert green
ACCENT_AMBER = "#ffb000"     # Warning amber
ACCENT_RED = "#ff3333"       # Critical error red
FONT_FAMILY = "Courier"

PAYLOAD_EXTENSIONS = {
    ".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".bat", ".cmd", ".ps1", ".sh", ".jar", ".bin", ".iso",
    ".js", ".vbs", ".scr", ".com", ".py", ".whl", ".crt", ".pem",
}

HOST_RE = re.compile(
    r"^[A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
    r"(\.[A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)+\$"
)

BAD_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
TEMPLATES = ("Classic", "Minimal", "Banner")


# ======================================================================
# URL validation & Sanitisation
# ======================================================================

def validate_url(raw: str) -> tuple[bool, str]:
    """Validate and normalise a URL. Returns (ok, message_or_normalised)."""
    raw = (raw or "").strip()
    if not raw:
        return False, "[-] ERROR: URL field is empty."

    if "://" not in raw:
        raw = "https://" + raw

    try:
        parsed = urlparse(raw)
    except ValueError as exc:
        return False, f"[-] PARSE EXCEPTION: {exc}"

    if parsed.scheme.lower() != "https":
        return False, f"[-] PROTOCOL ERROR: Only HTTPS accepted (got '{parsed.scheme or 'none'}')."

    host = parsed.hostname or ""
    if not host:
        return False, "[-] HOST ERROR: URL lacks a valid target host."
    if not HOST_RE.match(host):
        return False, f"[-] HOST ERROR: Malformed hostname syntax: '{host}'"
    if "." not in host:
        return False, f"[-] HOST ERROR: Hostname '{host}' is missing a TLD separator."

    path = (parsed.path or "").lower()
    for ext in PAYLOAD_EXTENSIONS:
        if path.endswith(ext):
            return False, f"[-] PAYLOAD WARNING: Target ends with '{ext}'. Direct payloads blocked."

    query = (parsed.query or "").lower()
    if "download=1" in query or "download=true" in query:
        return False, "[-] QUERY WARNING: Explicit download flags flagged in query string."

    normalised = f"{parsed.scheme.lower()}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        normalised += "?" + parsed.query
    return True, normalised


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe .pdf filename."""
    name = (name or "").strip() or "awareness_simulation.pdf"
    name = BAD_FILENAME_CHARS.sub("_", name)
    name = name.strip(" .") or "awareness_simulation.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


# ======================================================================
# History Persistence
# ======================================================================

def load_history() -> list[str]:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return [str(x) for x in data][:MAX_HISTORY]
    except (OSError, ValueError):
        pass
    return []


def save_history(items: list[str]) -> None:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as fh:
            json.dump(items[:MAX_HISTORY], fh, indent=2)
    except OSError:
        pass


# ======================================================================
# PDF Generation Engine
# ======================================================================

def _styles(accent: str):
    base = getSampleStyleSheet()
    accent_col = HexColor(accent)

    title = ParagraphStyle(
        "BigTitle", parent=base["Title"],
        fontSize=22, leading=26, alignment=TA_CENTER,
        textColor=accent_col, spaceAfter=6, fontName="Helvetica-Bold"
    )
    subtitle = ParagraphStyle(
        "Sub", parent=base["Normal"],
        fontSize=11, leading=15, alignment=TA_CENTER,
        textColor="#888888", spaceAfter=14, fontName="Helvetica"
    )
    body = ParagraphStyle(
        "Body", parent=base["Normal"],
        fontSize=11, leading=16, spaceAfter=10, alignment=TA_LEFT,
        fontName="Helvetica"
    )
    label = ParagraphStyle(
        "Label", parent=base["Normal"],
        fontSize=10, leading=13, textColor="#555555",
        spaceBefore=12, spaceAfter=2, fontName="Helvetica-Bold"
    )
    url = ParagraphStyle(
        "URLText", parent=base["Normal"],
        fontName="Courier-Bold", fontSize=12, leading=16,
        textColor=accent_col,
    )
    note = ParagraphStyle(
        "Note", parent=base["Normal"],
        fontSize=9, leading=13, textColor="#444444",
        spaceBefore=14, fontName="Helvetica-Oblique"
    )
    banner = ParagraphStyle(
        "Banner", parent=base["Normal"],
        fontSize=10, leading=14, alignment=TA_CENTER,
        textColor="#ffffff", backColor=accent_col,
        borderPadding=6, spaceAfter=14, fontName="Helvetica-Bold"
    )
    return {
        "title": title, "subtitle": subtitle, "body": body,
        "label": label, "url": url, "note": note, "banner": banner
    }


def build_pdf(out_path: str, url: str, template: str = "Classic",
              campaign: str = "", recipient_note: str = "",
              accent: str = "#0b3d91") -> None:
    """Compiles the secure awareness PDF document using ReportLab."""
    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )
    st = _styles(accent)
    story = []

    # Metadata headers if supplied
    if campaign:
        story.append(Paragraph(f"CAMPAIGN ID: {campaign.upper()}", st["subtitle"]))

    if template == "Banner":
        story.append(Paragraph("SECURITY AWARENESS DRILL — AUTHORIZED SIMULATION", st["banner"]))
        story.append(Paragraph("SIMULATION NOTICE", st["title"]))
    elif template == "Minimal":
        story.append(Paragraph("SECURITY DRILL NOTIFICATION", st["title"]))
        story.append(HRFlowable(width="100%", thickness=1, color=HexColor(accent), spaceBefore=2, spaceAfter=12))
    else:  # Classic
        story.append(Paragraph("SECURITY AWARENESS EXERCISE", st["title"]))
        story.append(Paragraph("This document is part of an authorized organizational security test.", st["subtitle"]))
        story.append(HRFlowable(width="80%", thickness=0.5, color="#cccccc", spaceAfter=14))

    # Body Content
    intro_text = (
        "You have opened a document distributed as part of our company-wide "
        "cybersecurity awareness program. No malicious payload was executed, "
        "and your system remains completely secure."
    )
    story.append(Paragraph(intro_text, st["body"]))

    explanation_text = (
        "During standard operations, simulated phishing tests measure organizational "
        "preparedness against social engineering attacks. If this had been a real threat, "
        "visiting unfamiliar links could have exposed credentials or corporate assets."
    )
    story.append(Paragraph(explanation_text, st["body"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("TARGET REFERENCE URL (PLAINTEXT ONLY):", st["label"]))
    story.append(Paragraph(url, st["url"]))
    story.append(Spacer(1, 15))

    if recipient_note:
        story.append(Paragraph(f"<b>Custom Directive / Note:</b> {recipient_note}", st["body"]))

    guidance_text = (
        "<b>Key Takeaways:</b><br/>"
        "• Always verify sender authenticity before clicking links.<br/>"
        "• Inspect URLs carefully for typosquatting or masked domains.<br/>"
        "• Report suspicious correspondence immediately to InfoSec."
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph(guidance_text, st["body"]))

    footer_note = (
        "[GUARANTEE] Generated locally via static document compiler. "
        "Zero network requests executed. Zero active code bindings embedded."
    )
    story.append(Paragraph(footer_note, st["note"]))

    doc.build(story)


# ======================================================================
# Hacker Terminal GUI Application
# ======================================================================

class HackerPDFApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("780x720")  # Fixed geometry specification string
        self.minsize(720, 680)
        self.configure(bg=BG_COLOR)

        self.history = load_history()

        # Tkinter variables
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self.on_url_changed)

        self.filename_var = tk.StringVar(value="awareness_drill.pdf")
        self.folder_var = tk.StringVar(value=os.path.expanduser("~"))
        self.campaign_var = tk.StringVar()
        self.template_var = tk.StringVar(value=TEMPLATES[0])
        self.accent_var = tk.StringVar(value="#00ff66")

        self.setup_styles()
        self.build_ui()
        self.refresh_history_dropdown()

    def setup_styles(self):
        """Configure TTK widgets for dark hacker theme."""
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=BG_COLOR, foreground=FG_COLOR, font=(FONT_FAMILY, 10))
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR, font=(FONT_FAMILY, 10, "bold"))
        style.configure("Dim.TLabel", background=BG_COLOR, foreground=TEXT_DIM, font=(FONT_FAMILY, 9))
        style.configure("TFrame", background=BG_COLOR)
        style.configure("TLabelframe", background=BG_COLOR, foreground=FG_COLOR, bordercolor=TEXT_DIM, relief="solid")
        style.configure("TLabelframe.Label", background=BG_COLOR, foreground=FG_COLOR, font=(FONT_FAMILY, 10, "bold"))
        
        style.configure("TButton", background=PANEL_BG, foreground=FG_COLOR, bordercolor=TEXT_DIM, focusthickness=1, focuscolor=FG_COLOR, font=(FONT_FAMILY, 9, "bold"))
        style.map("TButton", background=[("active", TEXT_DIM)], foreground=[("active", "#000000")])

        style.configure("TCombobox", fieldbackground=PANEL_BG, background=PANEL_BG, foreground=FG_COLOR, selectbackground=TEXT_DIM)
        style.configure("TEntry", fieldbackground=PANEL_BG, foreground=FG_COLOR, insertcolor=FG_COLOR)

    def build_ui(self):
        main_frame = ttk.Frame(self, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header Title Banner
        header_lbl = tk.Label(
            main_frame, 
            text=">>> SEC-OPS // SIMULATED AWARENESS DOCUMENT COMPILER v3.0 <<<",
            bg=BG_COLOR, fg=FG_COLOR, font=(FONT_FAMILY, 11, "bold")
        )
        header_lbl.pack(pady=(0, 10))

        # --- SECTION 1: Target Configuration ---
        cfg_frame = ttk.LabelFrame(main_frame, text="[ TARGET CONFIGURATION ]", padding=10)
        cfg_frame.pack(fill=tk.X, pady=5)

        # URL Input
        ttk.Label(cfg_frame, text="TARGET URL (HTTPS):").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.url_entry = ttk.Entry(cfg_frame, textvariable=self.url_var, width=55)
        self.url_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=4)

        # History dropdown
        self.history_combo = ttk.Combobox(cfg_frame, state="readonly", width=18)
        self.history_combo.grid(row=0, column=2, padx=5, pady=4)
        self.history_combo.bind("<<ComboboxSelected>>", self.on_history_selected)

        # Validation status feedback label
        self.status_lbl = tk.Label(cfg_frame, text="[STATUS: WAITING FOR INPUT]", bg=BG_COLOR, fg=TEXT_DIM, font=(FONT_FAMILY, 9, "bold"), anchor="w")
        self.status_lbl.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)

        cfg_frame.columnconfigure(1, weight=1)

        # --- SECTION 2: Output Parameters ---
        out_frame = ttk.LabelFrame(main_frame, text="[ OUTPUT PARAMETERS & DESTINATION ]", padding=10)
        out_frame.pack(fill=tk.X, pady=5)

        ttk.Label(out_frame, text="FILENAME:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(out_frame, textvariable=self.filename_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(out_frame, text="DESTINATION DIR:").grid(row=1, column=0, sticky=tk.W, pady=4)
        dir_entry = ttk.Entry(out_frame, textvariable=self.folder_var, width=45)
        dir_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=4)
        ttk.Button(out_frame, text="BROWSE...", command=self.browse_folder).grid(row=1, column=2, padx=5, pady=4)

        out_frame.columnconfigure(1, weight=1)

        # --- SECTION 3: Campaign Settings ---
        meta_frame = ttk.LabelFrame(main_frame, text="[ TEMPLATE & CAMPAIGN METADATA ]", padding=10)
        meta_frame.pack(fill=tk.X, pady=5)

        ttk.Label(meta_frame, text="TEMPLATE:").grid(row=0, column=0, sticky=tk.W, pady=4)
        t_box = ttk.Combobox(meta_frame, textvariable=self.template_var, values=TEMPLATES, state="readonly", width=15)
        t_box.grid(row=0, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(meta_frame, text="CAMPAIGN ID:").grid(row=0, column=2, sticky=tk.W, padx=15, pady=4)
        ttk.Entry(meta_frame, textvariable=self.campaign_var, width=20).grid(row=0, column=3, sticky=tk.W, padx=5, pady=4)

        ttk.Label(meta_frame, text="ACCENT THEME:").grid(row=1, column=0, sticky=tk.W, pady=4)
        accent_box = ttk.Combobox(meta_frame, textvariable=self.accent_var, values=["#00ff66", "#00bfff", "#ffb000", "#ff3333", "#9933ff"], state="readonly", width=15)
        accent_box.grid(row=1, column=1, sticky=tk.W, padx=5, pady=4)

        # Optional recipient note box
        ttk.Label(meta_frame, text="RECIPIENT NOTE:").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.note_text = tk.Text(meta_frame, height=3, width=45, bg=PANEL_BG, fg=FG_COLOR, insertbackground=FG_COLOR, font=(FONT_FAMILY, 9))
        self.note_text.grid(row=2, column=1, columnspan=3, sticky=tk.EW, padx=5, pady=4)

        meta_frame.columnconfigure(1, weight=1)

        # --- SECTION 4: Execution / Action Trigger ---
        act_frame = ttk.Frame(main_frame, padding=5)
        act_frame.pack(fill=tk.X, pady=10)

        compile_btn = ttk.Button(act_frame, text="[ COMPILE SECURE PDF ]", command=self.compile_pdf)
        compile_btn.pack(side=tk.RIGHT, ipadx=10, ipady=5)

        # Console / Terminal Log Output Box
        log_frame = ttk.LabelFrame(main_frame, text="[ TERMINAL LOG ]", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.console = tk.Text(log_frame, height=7, bg="#050806", fg=TEXT_DIM, font=(FONT_FAMILY, 9), state=tk.NORMAL)
        self.console.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.console.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.console.configure(yscrollcommand=scroll.set)

        self.log("System initialized. Secure environment active. Ready for input.")

    def log(self, msg: str):
        self.console.configure(state=tk.NORMAL)
        self.console.insert(tk.END, f">>> {msg}\n")
        self.console.see(tk.END)
        self.console.configure(state=tk.DISABLED)

    def browse_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get())
        if chosen:
            self.folder_var.set(chosen)
            self.log(f"Output directory re-routed to: {chosen}")

    def on_url_changed(self, *args):
        raw = self.url_var.get()
        ok, res = validate_url(raw)
        if not raw.strip():
            self.status_lbl.config(text="[STATUS: WAITING FOR INPUT]", fg=TEXT_DIM)
        elif ok:
            self.status_lbl.config(text="[STATUS: URL VERIFIED & SECURE]", fg=ACCENT_GREEN)
        else:
            self.status_lbl.config(text=res, fg=ACCENT_RED)

    def refresh_history_dropdown(self):
        if self.history:
            self.history_combo["values"] = self.history
            self.history_combo.set("[ SELECT RECENT URL ]")
        else:
            self.history_combo["values"] = ["No history found"]
            self.history_combo.set("No history found")

    def on_history_selected(self, event):
        selected = self.history_combo.get()
        if selected and selected != "No history found" and not selected.startswith("["):
            self.url_var.set(selected)
            self.log(f"Loaded target URL from history index: {selected}")

    def compile_pdf(self):
        raw_url = self.url_var.get()
        ok, result = validate_url(raw_url)

        if not ok:
            messagebox.showerror("Validation Failure", f"Target rejected by security controller:\n\n{result}")
            self.log(f"Compilation aborted. Reason: {result}")
            return

        target_url = result
        filename = sanitize_filename(self.filename_var.get())
        folder = self.folder_var.get()

        if not os.path.isdir(folder):
            messagebox.showerror("Path Error", f"Target directory does not exist:\n{folder}")
            return

        out_path = os.path.join(folder, filename)

        if os.path.exists(out_path):
            if not messagebox.askyesno("Overwrite Warning", f"File already exists:\n{out_path}\n\nOverwrite target?"):
                self.log("Compilation cancelled by operator (file conflict).")
                return

        # Update history
        if target_url in self.history:
            self.history.remove(target_url)
        self.history.insert(0, target_url)
        save_history(self.history)
        self.refresh_history_dropdown()

        # Build execution payload
        try:
            self.log(f"Compiling PDF -> {out_path}")
            build_pdf(
                out_path=out_path,
                url=target_url,
                template=self.template_var.get(),
                campaign=self.campaign_var.get().strip(),
                recipient_note=self.note_text.get("1.0", tk.END).strip(),
                accent=self.accent_var.get()
            )
            self.log("SUCCESS: Secure awareness PDF successfully generated.")
            messagebox.showinfo("Compilation Complete", f"PDF successfully compiled and secured at:\n{out_path}")
        except Exception as exc:
            self.log(f"CRITICAL ERROR during compilation: {exc}")
            messagebox.showerror("Compilation Exception", f"An error occurred while compiling the document:\n{exc}")


# ======================================================================
# Main Execution Entry Point
# ======================================================================

if __name__ == "__main__":
    app = HackerPDFApp()
    app.mainloop()