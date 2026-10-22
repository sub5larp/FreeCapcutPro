"""A small drag-and-drop desktop interface."""
from __future__ import annotations

import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

from . import __version__
from .engine import Cancelled, next_output, recover, resource_root

BG = "#101722"
PANEL = "#192331"
TEXT = "#eef3f8"
MUTED = "#9caec1"
ACCENT = "#72e3c1"


class App:
    def __init__(self, initial=None):
        self.root = TkinterDnD.Tk()
        self.root.title(f"CapCut Cache Repair {__version__}")
        self.root.geometry("720x620")
        self.root.minsize(660, 610)
        self.root.configure(bg=BG)
        icon = resource_root() / "assets" / "app.ico"
        if icon.exists():
            self.root.iconbitmap(str(icon))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False
        self.closing = False
        self.source = None
        self.output_directory = None
        self.result = None
        self.filename = tk.StringVar(value="No file selected")
        self.file_detail = tk.StringVar(value="Choose a preprocessed cache MP4 to begin.")
        self.folder_label = tk.StringVar(value="Same folder as the original")
        self.status = tk.StringVar(value="Ready when you are.")
        self.detail = tk.StringVar(value="Your original file stays untouched.")
        self.percent = tk.DoubleVar(value=0)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Repair.Horizontal.TProgressbar", background=ACCENT, troughcolor=PANEL, bordercolor=PANEL, lightcolor=ACCENT, darkcolor=ACCENT)
        outer = tk.Frame(self.root, bg=BG, padx=30, pady=24)
        outer.pack(fill="both", expand=True)
        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x")
        tk.Label(header, text="CapCut Cache Repair", font=("Segoe UI", 23, "bold"), bg=BG, fg=TEXT).pack(side="left")
        self.button(header, "About", self.about, small=True).pack(side="right", pady=6)
        tk.Label(outer, text="Turn a preprocessed cache into a playable MP4.", font=("Segoe UI", 11), bg=BG, fg=MUTED).pack(anchor="w", pady=(5, 22))

        self.drop = tk.Frame(outer, bg=PANEL, highlightbackground="#385463", highlightthickness=1, height=170)
        self.drop.pack(fill="x")
        self.drop.pack_propagate(False)
        self.drop_title = tk.Label(self.drop, text="Drop your cache MP4 here", font=("Segoe UI", 16, "bold"), bg=PANEL, fg=TEXT)
        self.drop_title.pack(pady=(24, 4))
        drop_subtitle = tk.Label(self.drop, text="or choose a file from your computer", font=("Segoe UI", 10), bg=PANEL, fg=MUTED)
        drop_subtitle.pack()
        self.browse_button = self.button(self.drop, "Choose MP4", self.browse)
        self.browse_button.pack(pady=14)
        for widget in (self.root, self.drop, self.drop_title, drop_subtitle, self.browse_button):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self.drop_file)

        tk.Label(outer, textvariable=self.filename, bg=BG, fg=TEXT, font=("Segoe UI", 10, "bold"), anchor="w", wraplength=640).pack(fill="x", pady=(18, 3))
        tk.Label(outer, textvariable=self.file_detail, bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w", wraplength=640).pack(fill="x")

        folder = tk.Frame(outer, bg=BG)
        folder.pack(fill="x", pady=(18, 16))
        left = tk.Frame(folder, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="SAVE TO", bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(left, textvariable=self.folder_label, bg=BG, fg=TEXT, font=("Segoe UI", 9), wraplength=450, anchor="w").pack(anchor="w", pady=(4, 0))
        self.folder_button = self.button(folder, "Change folder", self.choose_folder, small=True)
        self.folder_button.pack(side="right")

        ttk.Progressbar(outer, variable=self.percent, maximum=100, style="Repair.Horizontal.TProgressbar").pack(fill="x", pady=(0, 10))
        self.status_label = tk.Label(outer, textvariable=self.status, bg=BG, fg=TEXT, font=("Segoe UI", 11, "bold"), anchor="w")
        self.status_label.pack(fill="x")
        tk.Label(outer, textvariable=self.detail, bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w", justify="left", wraplength=640).pack(fill="x", pady=(5, 14))

        actions = tk.Frame(outer, bg=BG)
        actions.pack(side="bottom", fill="x", pady=(6, 0))
        self.open_button = self.button(actions, "Open output folder", self.open_output)
        self.open_button.pack(side="left")
        self.open_button.configure(state="disabled")
        self.cancel_button = self.button(actions, "Cancel", self.cancel)
        self.cancel_button.pack(side="right", padx=(10, 0))
        self.cancel_button.configure(state="disabled")
        self.convert_button = self.button(actions, "Convert to MP4", self.convert, accent=True)
        self.convert_button.pack(side="right")
        self.convert_button.configure(state="disabled")
        self.root.after(70, self.poll)
        if initial:
            self.root.after(150, lambda: self.select_file(initial))

    def button(self, parent, text, command, accent=False, small=False):
        return tk.Button(parent, text=text, command=command, font=("Segoe UI", 9 if small else 10, "bold"), bg=ACCENT if accent else "#263549", fg=BG if accent else TEXT, activebackground="#9df0d6" if accent else "#354b65", activeforeground=BG if accent else TEXT, disabledforeground="#647386", relief="flat", borderwidth=0, cursor="hand2", padx=14, pady=9 if small else 11, takefocus=True)

    def drop_file(self, event):
        if self.busy:
            return "break"
        paths = self.root.tk.splitlist(event.data)
        if len(paths) != 1:
            self.error("Drop one MP4 file at a time.")
        else:
            self.select_file(paths[0])
        return "copy"

    def browse(self):
        path = filedialog.askopenfilename(parent=self.root, title="Choose a CapCut cache MP4", filetypes=[("MP4 video", "*.mp4"), ("All files", "*.*")])
        if path:
            self.select_file(path)

    def select_file(self, path):
        if self.busy:
            return
        path = Path(path)
        if not path.is_file() or path.suffix.lower() != ".mp4":
            self.clear_selection()
            self.error("Choose an existing MP4 file.")
            return
        if path.name.lower().endswith(".alpha.mp4"):
            self.clear_selection()
            self.error("Choose the main cache MP4, not its alpha sidecar.")
            return
        self.source = path.resolve()
        self.filename.set(path.name)
        self.file_detail.set(f"{path.stat().st_size / 1048576:.1f} MB  |  {path.parent}")
        self.status.set("Ready to convert")
        self.detail.set("The restored video and audio will be checked before saving.")
        self.percent.set(0)
        self.convert_button.configure(state="normal")
        self.status_label.configure(fg=TEXT)

    def clear_selection(self):
        self.source = None
        self.filename.set("No file selected")
        self.file_detail.set("Choose a preprocessed cache MP4 to begin.")
        self.convert_button.configure(state="disabled")

    def choose_folder(self):
        path = filedialog.askdirectory(parent=self.root, title="Choose an output folder")
        if path:
            self.output_directory = Path(path)
            self.folder_label.set(str(path))

    def set_busy(self, value):
        self.busy = value
        for button in (self.browse_button, self.folder_button):
            button.configure(state="disabled" if value else "normal")
        self.convert_button.configure(state="disabled" if value or not self.source else "normal")
        self.cancel_button.configure(state="normal" if value else "disabled")

    def convert(self):
        if self.busy or self.source is None:
            return
        self.set_busy(True)
        self.open_button.configure(state="disabled")
        self.cancel_event.clear()
        self.percent.set(0)
        self.status_label.configure(fg=TEXT)
        self.detail.set("Restoring without re-encoding. This stays on your computer.")
        source = self.source
        destination = next_output(source, self.output_directory)

        def worker():
            try:
                report = recover(source, destination, lambda m, p: self.events.put(("progress", m, p)), self.cancel_event)
                self.events.put(("done", destination, report))
            except Cancelled:
                self.events.put(("cancelled",))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "progress":
                    self.status.set(event[1])
                    self.percent.set(event[2] * 100)
                else:
                    self.set_busy(False)
                    if self.closing:
                        self.root.destroy()
                        return
                    if event[0] == "done":
                        self.result = event[1]
                        self.status.set("Your MP4 is ready")
                        self.status_label.configure(fg=ACCENT)
                        self.detail.set(f"Saved {event[1].name}\nVideo and audio verified. Original file unchanged.")
                        self.percent.set(100)
                        self.open_button.configure(state="normal")
                    elif event[0] == "cancelled":
                        self.status.set("Conversion cancelled")
                        self.detail.set("No converted file was saved.")
                        self.percent.set(0)
                    else:
                        self.error(event[1])
        except queue.Empty:
            pass
        self.root.after(70, self.poll)

    def error(self, message):
        self.status.set("Could not convert this file")
        self.status_label.configure(fg="#ffbdab")
        self.detail.set(message.splitlines()[0])
        self.percent.set(0)

    def cancel(self):
        self.cancel_event.set()
        self.status.set("Cancelling...")
        self.cancel_button.configure(state="disabled")

    def close(self):
        if self.busy:
            self.closing = True
            self.cancel()
        else:
            self.root.destroy()

    def open_output(self):
        if self.result:
            os.startfile(str(self.result.parent))

    def about(self):
        messagebox.showinfo("About CapCut Cache Repair", f"CapCut Cache Repair {__version__}\n\nLocal recovery for supported BDVE cache videos.\nNo uploads. No re-encoding.\n\nIncludes Python, Tcl/Tk, TkinterDnD2 and FFmpeg.\nFFmpeg libraries are licensed under LGPL v3 or later.\nSee THIRD_PARTY.md and licenses in the source package.\n\nIndependent project; not affiliated with CapCut.", parent=self.root)

    def run(self):
        self.root.mainloop()
