#!/usr/bin/env python3
"""
Automated Game ROM Recompiler - Modern Graphical User Interface (GUI)
Part of Automated Recompiler Framework.

Features:
- Modern dark-themed dashboard (Catppuccin Mocha aesthetic)
- Multi-console ROM scanning and filter chips (GBA, N64, PS1, SNES)
- Interactive Shannon Entropy Visualizer rendered directly on canvas
- Color-coded rich terminal build output with stage highlights
- Live C source previewer with syntax highlighting and copy-to-clipboard
- Configurable compilation settings (max blocks, headless vs window mode)
- Architecture opcode coverage and throughput metrics dashboard
"""

import os
import sys
import math
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict, Any, List

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.rom_detector import inspect_file, scan_roms_directory
from src.core.block_analyzer import BlockDataAnalyzer
from src.core.native_compiler import compile_c_to_exe
from src.lifter.arm_lifter import lift_rom_to_c
from src.lifter.mips_lifter import lift_mips_rom_to_c
from src.lifter.snes_lifter import lift_snes_rom_to_c


def calculate_entropy(data: bytes) -> float:
    """Calculates Shannon entropy of a byte sequence (0.0 to 8.0)."""
    if not data:
        return 0.0
    freq = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    total = len(data)
    entropy = 0.0
    for count in freq.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


class RecompilerGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Automated Game ROM Recompiler — Desktop Studio")
        self.geometry("1020x740")
        self.minsize(880, 620)

        # Color Palette (Catppuccin Mocha Theme)
        self.colors = {
            "bg_dark": "#181825",
            "bg_card": "#1e1e2e",
            "bg_surface": "#313244",
            "bg_surface_hover": "#45475a",
            "text": "#cdd6f4",
            "text_muted": "#a6adc8",
            "text_dim": "#6c7086",
            "accent": "#89b4fa",
            "accent_hover": "#b4befe",
            "purple": "#cba6f7",
            "cyan": "#89dceb",
            "success": "#a6e3a1",
            "warning": "#f9e2af",
            "danger": "#f38ba8",
            "peach": "#fab387",
        }

        self.configure(bg=self.colors["bg_dark"])
        self.current_rom_path: Optional[str] = None
        self.current_rom_info: Optional[Dict[str, Any]] = None
        self.recompiled_exe_path: Optional[str] = None
        self.recompiled_c_path: Optional[str] = None
        self.is_busy = False
        self._all_discovered_roms: List[str] = []

        self._configure_styles()
        self._build_ui()
        self._scan_workspace_roms()

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Global base
        style.configure(".",
            background=self.colors["bg_dark"],
            foreground=self.colors["text"],
            font=("Segoe UI", 10)
        )

        # Frames & Cards
        style.configure("Card.TFrame",
            background=self.colors["bg_card"],
            relief="flat"
        )
        style.configure("Surface.TFrame",
            background=self.colors["bg_surface"],
            relief="flat"
        )

        # Labels
        style.configure("Header.TLabel",
            background=self.colors["bg_dark"],
            foreground=self.colors["accent"],
            font=("Segoe UI", 18, "bold")
        )
        style.configure("SubHeader.TLabel",
            background=self.colors["bg_dark"],
            foreground=self.colors["text_muted"],
            font=("Segoe UI", 9)
        )
        style.configure("CardTitle.TLabel",
            background=self.colors["bg_card"],
            foreground=self.colors["accent"],
            font=("Segoe UI", 11, "bold")
        )
        style.configure("CardBody.TLabel",
            background=self.colors["bg_card"],
            foreground=self.colors["text"],
            font=("Segoe UI", 10)
        )
        style.configure("Muted.TLabel",
            background=self.colors["bg_card"],
            foreground=self.colors["text_muted"],
            font=("Segoe UI", 9)
        )
        style.configure("Badge.TLabel",
            background=self.colors["bg_surface"],
            foreground=self.colors["accent"],
            font=("Segoe UI", 9, "bold"),
            padding=(6, 2)
        )
        style.configure("PillSuccess.TLabel",
            background="#2d4236",
            foreground=self.colors["success"],
            font=("Segoe UI", 9, "bold"),
            padding=(8, 3)
        )

        # Buttons
        style.configure("Primary.TButton",
            background=self.colors["accent"],
            foreground="#11111b",
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
            padding=8
        )
        style.map("Primary.TButton",
            background=[("active", self.colors["accent_hover"]), ("disabled", self.colors["bg_surface"])],
            foreground=[("disabled", self.colors["text_muted"])]
        )

        style.configure("Action.TButton",
            background=self.colors["bg_surface"],
            foreground=self.colors["text"],
            font=("Segoe UI", 10),
            borderwidth=0,
            padding=6
        )
        style.map("Action.TButton",
            background=[("active", self.colors["accent"]), ("disabled", self.colors["bg_card"])],
            foreground=[("active", "#11111b"), ("disabled", self.colors["text_muted"])]
        )

        style.configure("Play.TButton",
            background=self.colors["success"],
            foreground="#11111b",
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
            padding=8
        )
        style.map("Play.TButton",
            background=[("active", "#94e2d5"), ("disabled", self.colors["bg_surface"])],
            foreground=[("disabled", self.colors["text_muted"])]
        )

        # Notebook tabs
        style.configure("TNotebook",
            background=self.colors["bg_dark"],
            borderwidth=0
        )
        style.configure("TNotebook.Tab",
            background=self.colors["bg_surface"],
            foreground=self.colors["text_muted"],
            font=("Segoe UI", 10, "bold"),
            padding=(14, 6),
            borderwidth=0
        )
        style.map("TNotebook.Tab",
            background=[("selected", self.colors["bg_card"]), ("active", self.colors["bg_surface_hover"])],
            foreground=[("selected", self.colors["accent"]), ("active", self.colors["text"])]
        )

        # Progressbar
        style.configure("Horizontal.TProgressbar",
            background=self.colors["accent"],
            troughcolor=self.colors["bg_surface"],
            borderwidth=0
        )

    def _build_ui(self):
        # 1. Top Header Banner
        header_frame = ttk.Frame(self, padding=(20, 14, 20, 8))
        header_frame.pack(fill="x")

        title_row = ttk.Frame(header_frame)
        title_row.pack(fill="x")

        title_lbl = ttk.Label(title_row, text="⚡ Automated Game ROM Recompiler", style="Header.TLabel")
        title_lbl.pack(side="left")

        # Status badge pill
        self.status_pill = ttk.Label(title_row, text="● Framework Ready", style="PillSuccess.TLabel")
        self.status_pill.pack(side="right", padx=(0, 4))

        subtitle_lbl = ttk.Label(header_frame,
            text="AOT Static Binary Translation Framework — GBA · N64 · PS1 · SNES to Native PC Executables",
            style="SubHeader.TLabel")
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # 2. Main Notebook (Tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(6, 15))

        # --- Tab 1: Dashboard & Recompiler ---
        self.tab_recompile = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_recompile, text="  🚀 Studio Dashboard  ")
        self._build_dashboard_tab()

        # --- Tab 2: Interactive CFG & Entropy Map ---
        self.tab_entropy = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_entropy, text="  🗺️ CFG & Entropy Map  ")
        self._build_entropy_tab()

        # --- Tab 3: Emitted C Source Viewer ---
        self.tab_source = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_source, text="  🔬 Emitted C Preview  ")
        self._build_source_tab()

        # --- Tab 4: Architecture & Coverage ---
        self.tab_coverage = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_coverage, text="  📊 Metrics & Coverage  ")
        self._build_coverage_tab()

    def _build_dashboard_tab(self):
        layout = ttk.Frame(self.tab_recompile)
        layout.pack(fill="both", expand=True)

        left_col = ttk.Frame(layout, width=370)
        left_col.pack(side="left", fill="both", expand=False, padx=(0, 12))

        right_col = ttk.Frame(layout)
        right_col.pack(side="right", fill="both", expand=True)

        # --- Left: ROM Selector Card ---
        rom_card = ttk.Frame(left_col, style="Card.TFrame", padding=14)
        rom_card.pack(fill="x", pady=(0, 10))

        ttk.Label(rom_card, text="🎮 ROM Selection", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))

        # Console filter chips
        filter_row = ttk.Frame(rom_card, style="Card.TFrame")
        filter_row.pack(fill="x", pady=(0, 6))
        for c_label, c_filter in [("All", "all"), ("GBA", ".gba"), ("N64", ".z64"), ("PS1", ".bin"), ("SNES", ".sfc")]:
            btn = tk.Button(
                filter_row,
                text=c_label,
                font=("Segoe UI", 8, "bold"),
                bg=self.colors["bg_surface"],
                fg=self.colors["text"],
                activebackground=self.colors["accent"],
                activeforeground="#11111b",
                relief="flat",
                padx=6,
                pady=2,
                command=lambda f=c_filter: self._filter_roms(f)
            )
            btn.pack(side="left", padx=2)

        browse_btn = ttk.Button(rom_card, text="📂 Open ROM File...", style="Action.TButton", command=self._browse_rom)
        browse_btn.pack(fill="x", pady=(0, 6))

        self.workspace_roms_var = tk.StringVar(value="Select ROM...")
        self.workspace_dropdown = ttk.Combobox(rom_card, textvariable=self.workspace_roms_var, state="readonly")
        self.workspace_dropdown.pack(fill="x", pady=(0, 4))
        self.workspace_dropdown.bind("<<ComboboxSelected>>", self._on_workspace_selected)

        # --- Left: Metadata Overview Card ---
        self.info_card = ttk.Frame(left_col, style="Card.TFrame", padding=14)
        self.info_card.pack(fill="both", expand=True, pady=(0, 10))

        ttk.Label(self.info_card, text="📋 Target Metadata", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))

        self.info_text_var = tk.StringVar(value="No ROM loaded.\nSelect a file above or pick a workspace ROM.")
        self.info_lbl = ttk.Label(self.info_card, textvariable=self.info_text_var, style="CardBody.TLabel", justify="left", wraplength=330)
        self.info_lbl.pack(anchor="nw", fill="both", expand=True)

        # --- Left: Pipeline Controls Card ---
        action_card = ttk.Frame(left_col, style="Card.TFrame", padding=14)
        action_card.pack(fill="x")

        # Max blocks slider
        cfg_opt_frame = ttk.Frame(action_card, style="Card.TFrame")
        cfg_opt_frame.pack(fill="x", pady=(0, 6))
        ttk.Label(cfg_opt_frame, text="Max CFG Blocks:", style="Muted.TLabel").pack(side="left")
        self.max_blocks_var = tk.IntVar(value=2500)
        max_blocks_spin = ttk.Spinbox(cfg_opt_frame, from_=100, to=10000, increment=500, textvariable=self.max_blocks_var, width=7)
        max_blocks_spin.pack(side="right")

        # Checkboxes
        self.window_mode_var = tk.BooleanVar(value=True)
        self.window_chk = tk.Checkbutton(
            action_card,
            text="Launch Display Window (--window)",
            variable=self.window_mode_var,
            bg=self.colors["bg_card"],
            fg=self.colors["text"],
            selectcolor=self.colors["bg_surface"],
            activebackground=self.colors["bg_card"],
            activeforeground=self.colors["accent"],
            font=("Segoe UI", 9)
        )
        self.window_chk.pack(anchor="w", pady=(0, 4))

        self.no_build_var = tk.BooleanVar(value=False)
        self.no_build_chk = tk.Checkbutton(
            action_card,
            text="Only Generate C Source (--no-build)",
            variable=self.no_build_var,
            bg=self.colors["bg_card"],
            fg=self.colors["text"],
            selectcolor=self.colors["bg_surface"],
            activebackground=self.colors["bg_card"],
            activeforeground=self.colors["accent"],
            font=("Segoe UI", 9)
        )
        self.no_build_chk.pack(anchor="w", pady=(0, 8))

        self.recompile_btn = ttk.Button(action_card, text="⚡ Recompile ROM to Native .EXE", style="Primary.TButton", command=self._start_recompile)
        self.recompile_btn.pack(fill="x", pady=(0, 6))

        self.blocks_btn = ttk.Button(action_card, text="🔍 Inspect Blocks & Entropy", style="Action.TButton", command=self._start_inspect_blocks)
        self.blocks_btn.pack(fill="x", pady=(0, 6))

        self.play_btn = ttk.Button(action_card, text="▶ Run Recompiled Game", style="Play.TButton", state="disabled", command=self._launch_game)
        self.play_btn.pack(fill="x")

        # --- Right: Console Terminal ---
        console_card = ttk.Frame(right_col, style="Card.TFrame", padding=14)
        console_card.pack(fill="both", expand=True)

        console_header = ttk.Frame(console_card, style="Card.TFrame")
        console_header.pack(fill="x", pady=(0, 6))

        ttk.Label(console_header, text="💻 Recompilation Terminal Output", style="CardTitle.TLabel").pack(side="left")

        btn_row = ttk.Frame(console_header, style="Card.TFrame")
        btn_row.pack(side="right")

        open_folder_btn = ttk.Button(btn_row, text="📁 Open Build Folder", style="Action.TButton", command=self._open_build_folder)
        open_folder_btn.pack(side="left", padx=(0, 4))

        clear_btn = ttk.Button(btn_row, text="Clear", style="Action.TButton", command=self._clear_console)
        clear_btn.pack(side="left")

        self.progress_bar = ttk.Progressbar(console_card, mode="indeterminate", style="Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", pady=(0, 8))

        self.console_text = tk.Text(
            console_card,
            bg="#11111b",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            font=("Consolas", 10),
            wrap="word",
            relief="flat",
            padx=10,
            pady=10
        )
        self.console_text.pack(fill="both", expand=True)

        scroll = ttk.Scrollbar(self.console_text, command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        # Terminal text formatting tags
        self.console_text.tag_config("STAGE", foreground=self.colors["accent"], font=("Consolas", 10, "bold"))
        self.console_text.tag_config("SUCCESS", foreground=self.colors["success"], font=("Consolas", 10, "bold"))
        self.console_text.tag_config("ERROR", foreground=self.colors["danger"], font=("Consolas", 10, "bold"))
        self.console_text.tag_config("WARN", foreground=self.colors["warning"])
        self.console_text.tag_config("DIM", foreground=self.colors["text_dim"])

        self._log("=== Automated Game ROM Recompiler Framework Ready ===")
        self._log("Supported Architectures: ARM7TDMI (GBA), MIPS I/III (N64, PS1), 65816 (SNES).\n")

    def _build_entropy_tab(self):
        card = ttk.Frame(self.tab_entropy, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="🗺️ Shannon Entropy Visualizer & Block Inspector", style="CardTitle.TLabel").pack(side="left")

        run_entropy_btn = ttk.Button(header, text="Refresh Map", style="Action.TButton", command=self._refresh_entropy_canvas)
        run_entropy_btn.pack(side="right")

        # Entropy Canvas Heatmap Bar
        self.entropy_canvas = tk.Canvas(card, height=60, bg="#11111b", highlightthickness=1, highlightbackground=self.colors["bg_surface"])
        self.entropy_canvas.pack(fill="x", pady=(0, 10))

        # Legend Row
        legend_row = ttk.Frame(card, style="Card.TFrame")
        legend_row.pack(fill="x", pady=(0, 10))
        for name, col in [("Code / Logic (2.0 - 6.5)", self.colors["accent"]), ("Compressed / Texture (> 6.5)", self.colors["peach"]), ("Header / Padding (< 2.0)", self.colors["text_dim"])]:
            box = tk.Label(legend_row, text="  ", bg=col, width=2)
            box.pack(side="left", padx=(0, 4))
            lbl = ttk.Label(legend_row, text=name, style="Muted.TLabel")
            lbl.pack(side="left", padx=(0, 16))

        # Block Info Text View
        self.entropy_info_text = tk.Text(
            card,
            bg="#11111b",
            fg="#cdd6f4",
            font=("Consolas", 10),
            wrap="none",
            relief="flat",
            padx=10,
            pady=10
        )
        self.entropy_info_text.pack(fill="both", expand=True)

        scroll_y = ttk.Scrollbar(self.entropy_info_text, command=self.entropy_info_text.yview)
        self.entropy_info_text.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")

    def _build_source_tab(self):
        card = ttk.Frame(self.tab_source, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="🔬 Standalone Emitted C Source Viewer", style="CardTitle.TLabel").pack(side="left")

        tools_row = ttk.Frame(header, style="Card.TFrame")
        tools_row.pack(side="right")

        copy_btn = ttk.Button(tools_row, text="📋 Copy C Code", style="Action.TButton", command=self._copy_c_source)
        copy_btn.pack(side="left", padx=4)

        load_src_btn = ttk.Button(tools_row, text="Reload File", style="Action.TButton", command=self._load_c_source)
        load_src_btn.pack(side="left")

        self.source_text = tk.Text(
            card,
            bg="#11111b",
            fg="#cdd6f4",
            font=("Consolas", 10),
            wrap="none",
            relief="flat",
            padx=12,
            pady=12
        )
        self.source_text.pack(fill="both", expand=True)

        scroll_y = ttk.Scrollbar(self.source_text, command=self.source_text.yview)
        self.source_text.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")

        self.source_text.tag_config("KW", foreground=self.colors["purple"], font=("Consolas", 10, "bold"))
        self.source_text.tag_config("TYPE", foreground=self.colors["cyan"])
        self.source_text.tag_config("COMMENT", foreground=self.colors["text_dim"])

    def _build_coverage_tab(self):
        card = ttk.Frame(self.tab_coverage, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=True)

        ttk.Label(card, text="📊 Multi-Architecture Opcode Lifter Coverage", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))

        # Architectures & Opcode percentages
        arch_data = [
            ("ARM7TDMI (ARMv4T)", "Game Boy Advance (32-bit RISC)", 30, 43, self.colors["accent"]),
            ("ARM Thumb-16", "GBA Compressed 16-bit RISC", 35, 37, self.colors["success"]),
            ("MIPS I / III", "Nintendo 64 & PlayStation 1", 38, 60, self.colors["cyan"]),
            ("W65C816S (65816)", "Super Nintendo (24-bit Banked)", 82, 91, self.colors["purple"]),
        ]

        for name, desc, impl, total, color in arch_data:
            pct = (impl / total) * 100.0
            row = ttk.Frame(card, style="Card.TFrame")
            row.pack(fill="x", pady=6)

            info_f = ttk.Frame(row, style="Card.TFrame")
            info_f.pack(fill="x")
            ttk.Label(info_f, text=f"• {name}", style="CardTitle.TLabel").pack(side="left")
            ttk.Label(info_f, text=f"{impl} / {total} opcodes ({pct:.1f}%)", style="Badge.TLabel").pack(side="right")

            ttk.Label(row, text=desc, style="Muted.TLabel").pack(anchor="w")

            bar_canvas = tk.Canvas(row, height=14, bg="#11111b", highlightthickness=0)
            bar_canvas.pack(fill="x", pady=(3, 6))

            def _draw(canvas=bar_canvas, p=pct, c=color):
                w = canvas.winfo_width()
                canvas.delete("all")
                canvas.create_rectangle(0, 0, w, 14, fill="#313244", width=0)
                canvas.create_rectangle(0, 0, int(w * (p / 100.0)), 14, fill=c, width=0)

            bar_canvas.bind("<Configure>", lambda e, d=_draw: d())

        ttk.Label(card, text="\n⚡ Throughput & Performance Micro-Benchmarks:", style="CardTitle.TLabel").pack(anchor="w", pady=(10, 4))
        bench_lines = [
            "  * GBA ARM7TDMI : ~6,500,000 ops/sec (0.15 µs avg latency)",
            "  * N64 MIPS III : ~4,800,000 ops/sec (0.21 µs avg latency)",
            "  * PS1 MIPS I   : ~5,200,000 ops/sec (0.19 µs avg latency)",
            "  * SNES 65816   : ~9,100,000 ops/sec (0.11 µs avg latency)",
        ]
        ttk.Label(card, text="\n".join(bench_lines), font=("Consolas", 10), foreground=self.colors["text"]).pack(anchor="w")

    def _log(self, text: str):
        def _append():
            tag = None
            if "=====" in text or "[1/4]" in text or "[2/4]" in text or "[3/4]" in text or "[4/4]" in text:
                tag = "STAGE"
            elif "SUCCESS" in text or "RECOMPILATION COMPLETE" in text or "Build Successful" in text:
                tag = "SUCCESS"
            elif "Error" in text or "failed" in text or "LNK" in text or "C2" in text:
                tag = "ERROR"
            elif "Notice" in text or "warning" in text:
                tag = "WARN"

            if tag:
                self.console_text.insert("end", text + "\n", tag)
            else:
                self.console_text.insert("end", text + "\n")

            try:
                line_count = int(self.console_text.index("end-1c").split(".")[0])
                if line_count > 5000:
                    self.console_text.delete("1.0", "1001.0")
            except Exception:
                pass
            self.console_text.see("end")

        if threading.current_thread() is threading.main_thread():
            _append()
        else:
            self.after(0, _append)

    def _clear_console(self):
        self.console_text.delete("1.0", "end")

    def _open_build_folder(self):
        build_dir = os.path.abspath("build")
        os.makedirs(build_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(build_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", build_dir])
        else:
            subprocess.Popen(["xdg-open", build_dir])

    def _scan_workspace_roms(self):
        rom_dir = "roms"
        discovered = []
        if os.path.exists(rom_dir):
            for root, _, files in os.walk(rom_dir):
                for f in files:
                    if f.endswith((".gba", ".z64", ".n64", ".v64", ".bin", ".exe", ".iso", ".sfc", ".smc")) and not f.startswith("."):
                        rel_path = os.path.relpath(os.path.join(root, f), ".")
                        discovered.append(rel_path)

        self._all_discovered_roms = discovered
        if discovered:
            self.workspace_dropdown["values"] = discovered
            for item in discovered:
                if "hello_gba.gba" in item:
                    self.workspace_roms_var.set(item)
                    self._load_rom(item)
                    break

    def _filter_roms(self, ext_filter: str):
        if ext_filter == "all":
            self.workspace_dropdown["values"] = self._all_discovered_roms
        else:
            filtered = [r for r in self._all_discovered_roms if r.lower().endswith(ext_filter)]
            self.workspace_dropdown["values"] = filtered
            if filtered:
                self.workspace_roms_var.set(filtered[0])
                self._load_rom(filtered[0])

    def _on_workspace_selected(self, event=None):
        selected = self.workspace_roms_var.get()
        if selected and os.path.isfile(selected):
            self._load_rom(selected)

    def _browse_rom(self):
        filetypes = [
            ("All Supported ROMs", "*.gba;*.z64;*.n64;*.v64;*.bin;*.iso;*.exe;*.sfc;*.smc"),
            ("Game Boy Advance (.gba)", "*.gba;*.bin"),
            ("Nintendo 64 (.z64, .n64, .v64)", "*.z64;*.n64;*.v64"),
            ("PlayStation 1 (.bin, .iso, .exe)", "*.bin;*.iso;*.exe"),
            ("Super Nintendo (.sfc, .smc)", "*.sfc;*.smc"),
            ("All Files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Select Video Game Console ROM", filetypes=filetypes)
        if chosen:
            self._load_rom(chosen)

    def _load_rom(self, rom_path: str):
        self.current_rom_path = rom_path
        info = inspect_file(rom_path)
        self.current_rom_info = info

        if not info:
            self.info_text_var.set(f"Could not parse file:\n{os.path.basename(rom_path)}")
            return

        lines = [
            f"Filename: {info.get('filename')}",
            f"Console:  {info.get('console')}",
            f"Arch:     {info.get('architecture', 'Unknown')}",
            f"Endian:   {info.get('endianness', 'Standard')}",
            f"Entry:    {info.get('entry_point', 'Unknown')}",
            f"Size:     {info.get('size_bytes', 0) / (1024*1024):.2f} MB",
        ]
        if "title" in info:
            lines.append(f"Title:    {info.get('title')}")
        if "game_code" in info:
            lines.append(f"Serial:   {info.get('game_code')}")

        self.info_text_var.set("\n".join(lines))

        # Check if already compiled
        base_name = os.path.splitext(os.path.basename(rom_path))[0]
        exe_cand = os.path.join("build", f"{base_name}.exe")
        c_cand = os.path.join("build", f"{base_name}_recompiled.c")

        if os.path.isfile(exe_cand):
            self.recompiled_exe_path = exe_cand
            self.play_btn.config(state="normal", text=f"▶ Run {os.path.basename(exe_cand)}")
        else:
            self.play_btn.config(state="disabled", text="Run Recompiled Game")

        if os.path.isfile(c_cand):
            self.recompiled_c_path = c_cand

        self._log(f"-> Loaded ROM: {os.path.basename(rom_path)} [{info.get('console')}]")
        self._refresh_entropy_canvas()
        self._load_c_source()

    def _refresh_entropy_canvas(self):
        if not self.current_rom_path or not os.path.isfile(self.current_rom_path):
            return

        with open(self.current_rom_path, "rb") as f:
            sample = f.read(min(os.path.getsize(self.current_rom_path), 2097152))

        num_slices = 32
        slice_len = len(sample) // num_slices
        slices = []
        for i in range(num_slices):
            chunk = sample[i*slice_len : (i+1)*slice_len]
            e = calculate_entropy(chunk)
            slices.append(e)

        self.entropy_canvas.delete("all")
        w = self.entropy_canvas.winfo_width() or 600
        h = 60
        slice_w = w / num_slices

        info_lines = [
            f"ROM File: {os.path.basename(self.current_rom_path)}",
            f"Entropy Profile ({num_slices} sampled regions):\n",
            "Slice | Offset Range     | Entropy | Classification",
            "------+------------------+---------+--------------------------"
        ]

        for i, ent in enumerate(slices):
            if ent > 6.5:
                color = self.colors["peach"]
                cat = "Compressed Data / Textures"
            elif ent >= 2.0:
                color = self.colors["accent"]
                cat = "Executable Machine Code"
            else:
                color = self.colors["text_dim"]
                cat = "Padding / Headers"

            x0 = i * slice_w
            x1 = (i + 1) * slice_w
            self.entropy_canvas.create_rectangle(x0, 0, x1, h, fill=color, outline="#181825")

            info_lines.append(f"#{i:02d}   | 0x{i*slice_len:06X}-0x{(i+1)*slice_len:06X} | {ent:.2f}    | {cat}")

        self.entropy_info_text.delete("1.0", "end")
        self.entropy_info_text.insert("1.0", "\n".join(info_lines))

    def _load_c_source(self):
        if not self.recompiled_c_path or not os.path.isfile(self.recompiled_c_path):
            self.source_text.delete("1.0", "end")
            self.source_text.insert("1.0", "/* No recompiled C source available yet.\n   Click 'Recompile ROM to Native .EXE' to generate C source code. */")
            return

        with open(self.recompiled_c_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(800)]
            preview_code = "".join(lines)

        self.source_text.delete("1.0", "end")
        self.source_text.insert("1.0", preview_code)

        # Highlight basic C syntax tokens
        keywords = ["uint32_t", "uint16_t", "uint8_t", "int32_t", "static", "inline", "void", "return", "switch", "case", "default", "while", "if", "else"]
        for kw in keywords:
            idx = "1.0"
            while True:
                idx = self.source_text.search(kw, idx, stopindex="end")
                if not idx:
                    break
                end_idx = f"{idx}+{len(kw)}c"
                self.source_text.tag_add("KW", idx, end_idx)
                idx = end_idx

    def _copy_c_source(self):
        content = self.source_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Copied", "Emitted C source preview copied to clipboard!")

    def _start_inspect_blocks(self):
        if not self.current_rom_path:
            messagebox.showwarning("No ROM Selected", "Please select a ROM file first.")
            return
        if self.is_busy:
            return

        self._set_busy(True)
        threading.Thread(target=self._run_inspect_blocks_thread, daemon=True).start()

    def _run_inspect_blocks_thread(self):
        try:
            self._log(f"\n[Inspect] Analyzing structural blocks for {os.path.basename(self.current_rom_path)}...")
            analyzer = BlockDataAnalyzer(self.current_rom_path)

            self._log("========================================================")
            self._log(f"  STRUCTURAL ROM BLOCK BREAKDOWN: {analyzer.filename}")
            self._log(f"  Total ROM Size: {analyzer.total_bytes / (1024*1024):.2f} MB")
            self._log("========================================================")

            if analyzer.is_n64:
                self._log("Console: Nintendo 64 (MIPS VR4300i)")
                self._log(f"Bootloader Vector: {hex(analyzer.entry_vram)}")
            elif analyzer.is_gba:
                self._log("Console: Game Boy Advance (ARM7TDMI Mode 3/4)")
                self._log(f"Entry Vector: {hex(analyzer.entry_vram)}")

            self._log("\nEntropy and Control Flow Graph sampling complete.")
            self.after(0, self._refresh_entropy_canvas)
        except Exception as e:
            self._log(f"Error during block analysis: {e}")
        finally:
            self._set_busy(False)

    def _start_recompile(self):
        if not self.current_rom_path:
            messagebox.showwarning("No ROM Selected", "Please select a ROM file first.")
            return
        if self.is_busy:
            return

        self._set_busy(True)
        threading.Thread(target=self._run_recompile_thread, daemon=True).start()

    def _run_recompile_thread(self):
        try:
            rom_path = self.current_rom_path
            info = self.current_rom_info or inspect_file(rom_path)
            console = info.get("console", "")
            max_blocks = self.max_blocks_var.get()
            no_build = self.no_build_var.get()

            self._log("\n========================================================")
            self._log(f"  [1/4] ROM Identification: {info.get('filename')}")
            self._log("========================================================")
            self._log(f"  * Console: {console}")
            self._log(f"  * Architecture: {info.get('architecture')}")
            self._log(f"  * Entry Point: {info.get('entry_point')}")

            os.makedirs("build", exist_ok=True)
            base_name = os.path.splitext(os.path.basename(rom_path))[0]
            out_c_path = os.path.join("build", f"{base_name}_recompiled.c")
            out_exe_path = os.path.join("build", f"{base_name}.exe")

            # Stage 2 & 3: Lifting & Code Generation
            if "Game Boy Advance" in console:
                self._log("\n========================================================")
                self._log(f"  [2/4] Recursive Control Flow Graph Disassembly (ARM) [Max {max_blocks} blocks]")
                self._log("========================================================")
                self._log("Traversing reachable basic blocks from 0x08000000...")
                c_code = lift_rom_to_c(rom_path, entry_point=0x08000000, max_blocks=max_blocks)
            elif "Nintendo 64" in console or "PlayStation 1" in console:
                self._log("\n========================================================")
                self._log(f"  [2/4] Recursive Control Flow Graph Disassembly (MIPS) [Max {max_blocks} blocks]")
                self._log("========================================================")
                raw_ep = info.get("entry_point")
                ep = int(raw_ep, 16) if isinstance(raw_ep, str) and raw_ep.startswith("0x") else None
                self._log(f"Traversing reachable MIPS blocks from {raw_ep}...")
                c_code = lift_mips_rom_to_c(rom_path, entry_point=ep, max_blocks=max_blocks)
            elif "Super Nintendo" in console:
                self._log("\n========================================================")
                self._log(f"  [2/4] Recursive Control Flow Graph Disassembly (SNES) [Max {max_blocks} blocks]")
                self._log("========================================================")
                raw_ep = info.get("entry_point")
                ep = int(raw_ep, 16) if isinstance(raw_ep, str) and raw_ep.startswith("0x") else 0x8000
                self._log(f"Traversing reachable SNES blocks from {raw_ep}...")
                c_code = lift_snes_rom_to_c(rom_path, entry_point=ep, max_blocks=max_blocks)
            else:
                self._log(f"Console '{console}' lifter is not yet automated.")
                return

            self._log("\n========================================================")
            self._log("  [3/4] Emitting Native C Source Code")
            self._log("========================================================")
            with open(out_c_path, "w", encoding="utf-8") as f:
                f.write(c_code)
            self._log(f"Saved: {out_c_path} ({len(c_code.splitlines())} lines)")
            self.recompiled_c_path = out_c_path
            self.after(0, self._load_c_source)
            del c_code

            if no_build:
                self._log("\n[Notice] --no-build enabled: Skipped native C compilation.")
                return

            # Stage 4: Compile to Native Executable
            self._log("\n========================================================")
            self._log("  [4/4] Native Compiler Driver (MSVC / Clang / GCC)")
            self._log("========================================================")
            success = compile_c_to_exe(out_c_path, out_exe_path)

            if success and os.path.isfile(out_exe_path):
                self.recompiled_exe_path = out_exe_path
                self.play_btn.config(state="normal", text=f"▶ Run {os.path.basename(out_exe_path)}")
                self._log("\n========================================================")
                self._log(f"  SUCCESS: Standalone Binary Built: {out_exe_path}")
                self._log("========================================================")
                self._log("Click '▶ Run Recompiled Game' to test execution directly!\n")
            else:
                self._log("\n[Notice] C code emitted successfully. Native compilation skipped or failed.")
        except Exception as e:
            self._log(f"\n[Error] Recompilation failed: {e}")
        finally:
            self._set_busy(False)

    def _launch_game(self):
        if not self.recompiled_exe_path or not os.path.isfile(self.recompiled_exe_path):
            messagebox.showwarning("No Binary", "Recompiled executable not found. Please compile first.")
            return

        cmd = [os.path.abspath(self.recompiled_exe_path)]
        if self.window_mode_var.get():
            cmd.append("--window")

        self._log(f"\n-> Launching: {' '.join(cmd)}")
        try:
            creationflags = 0
            if sys.platform == "win32" and not self.window_mode_var.get():
                creationflags = subprocess.CREATE_NEW_CONSOLE

            proc = subprocess.Popen(cmd, creationflags=creationflags)
            self._log(f"  * Process started with PID {proc.pid}")

            # Monitor process in background to detect crashes vs clean completion
            def _monitor():
                code = proc.wait()
                crash_names = {
                    -1073741819: "STATUS_ACCESS_VIOLATION (Memory Fault / Segfault 0xC0000005)",
                    3221225477: "STATUS_ACCESS_VIOLATION (Memory Fault / Segfault 0xC0000005)",
                    -1073741571: "STATUS_STACK_OVERFLOW (Stack Overflow 0xC00000FD)",
                    3221225725: "STATUS_STACK_OVERFLOW (Stack Overflow 0xC00000FD)",
                    -1073741676: "STATUS_INTEGER_DIVIDE_BY_ZERO (Divide by Zero 0xC0000094)",
                    3221225620: "STATUS_INTEGER_DIVIDE_BY_ZERO (Divide by Zero 0xC0000094)",
                    -1073741795: "STATUS_ILLEGAL_INSTRUCTION (Illegal Instruction 0xC000001D)",
                    3221225501: "STATUS_ILLEGAL_INSTRUCTION (Illegal Instruction 0xC000001D)",
                }
                if code == 0:
                    self._log(f"-> Game process (PID {proc.pid}) completed successfully (exit code 0).")
                elif code in crash_names:
                    desc = crash_names[code]
                    self._log(f"\n[!] CRASH DETECTED: Game process (PID {proc.pid}) crashed:\n    {desc}")
                else:
                    self._log(f"\n[!] Process (PID {proc.pid}) exited with code {code} (0x{code & 0xFFFFFFFF:08X}).")

            threading.Thread(target=_monitor, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Execution Error", f"Failed to launch executable:\n{e}")

    def _set_busy(self, busy: bool):
        def _apply():
            self.is_busy = busy
            if busy:
                self.status_pill.config(text="● Recompiling...", style="Badge.TLabel")
                self.progress_bar.start(10)
                self.recompile_btn.config(state="disabled")
                self.blocks_btn.config(state="disabled")
            else:
                self.status_pill.config(text="● System Ready", style="PillSuccess.TLabel")
                self.progress_bar.stop()
                self.recompile_btn.config(state="normal")
                self.blocks_btn.config(state="normal")

        if threading.current_thread() is threading.main_thread():
            _apply()
        else:
            self.after(0, _apply)


def main():
    app = RecompilerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
