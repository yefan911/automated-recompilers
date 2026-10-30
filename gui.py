#!/usr/bin/env python3
"""
Automated Game ROM Recompiler - Graphical User Interface (GUI)
Part of Automated Recompiler Framework.

Provides an interactive desktop GUI for ROM scanning, header inspection,
entropy & block analysis, one-click ahead-of-time recompilation, and game launch.
"""

import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.rom_detector import inspect_file, scan_roms_directory
from src.core.block_analyzer import BlockDataAnalyzer
from src.core.native_compiler import compile_c_to_exe
from src.lifter.arm_lifter import lift_rom_to_c
from src.lifter.mips_lifter import lift_mips_rom_to_c


class RecompilerGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Automated Game ROM Recompiler")
        self.geometry("920x680")
        self.minsize(800, 580)

        # Color Palette (Dark Modern Theme)
        self.colors = {
            "bg_dark": "#181825",
            "bg_card": "#1e1e2e",
            "bg_surface": "#313244",
            "text": "#cdd6f4",
            "text_muted": "#a6adc8",
            "accent": "#89b4fa",
            "accent_hover": "#b4befe",
            "success": "#a6e3a1",
            "warning": "#f9e2af",
            "danger": "#f38ba8",
        }

        self.configure(bg=self.colors["bg_dark"])
        self.current_rom_path: Optional[str] = None
        self.current_rom_info: Optional[Dict[str, Any]] = None
        self.recompiled_exe_path: Optional[str] = None
        self.is_busy = False

        self._configure_styles()
        self._build_ui()
        self._scan_workspace_roms()

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".",
            background=self.colors["bg_dark"],
            foreground=self.colors["text"],
            font=("Segoe UI", 10)
        )

        style.configure("Card.TFrame",
            background=self.colors["bg_card"],
            relief="flat"
        )

        style.configure("Header.TLabel",
            background=self.colors["bg_dark"],
            foreground=self.colors["accent"],
            font=("Segoe UI", 16, "bold")
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

    def _build_ui(self):
        # Top Header
        top_frame = ttk.Frame(self, padding=(20, 15, 20, 5))
        top_frame.pack(fill="x")

        title_lbl = ttk.Label(top_frame, text="Automated Game ROM Recompiler", style="Header.TLabel")
        title_lbl.pack(anchor="w")

        subtitle_lbl = ttk.Label(top_frame,
            text="Static AOT Recompilation Framework (GBA, N64, PS1) -> Standalone Native Windows Binary",
            style="SubHeader.TLabel")
        subtitle_lbl.pack(anchor="w")

        # Main Layout: 2 Columns (Left: Selection & Info, Right: Console & Progress)
        content_frame = ttk.Frame(self, padding=(20, 10, 20, 15))
        content_frame.pack(fill="both", expand=True)

        left_col = ttk.Frame(content_frame)
        left_col.pack(side="left", fill="both", expand=False, padx=(0, 15))
        left_col.configure(width=380)

        right_col = ttk.Frame(content_frame)
        right_col.pack(side="right", fill="both", expand=True)

        # --- LEFT COLUMN: ROM File Selector Card ---
        rom_card = ttk.Frame(left_col, style="Card.TFrame", padding=15)
        rom_card.pack(fill="x", pady=(0, 10))

        ttk.Label(rom_card, text="ROM Selection", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))

        # Browse Button
        browse_btn = ttk.Button(rom_card, text="Open ROM File...", style="Action.TButton", command=self._browse_rom)
        browse_btn.pack(fill="x", pady=(0, 8))

        # Workspace Dropdown
        ttk.Label(rom_card, text="Or select discovered ROM from workspace:", style="Muted.TLabel").pack(anchor="w", pady=(2, 4))
        self.workspace_roms_var = tk.StringVar(value="Select ROM...")
        self.workspace_dropdown = ttk.Combobox(rom_card, textvariable=self.workspace_roms_var, state="readonly")
        self.workspace_dropdown.pack(fill="x", pady=(0, 6))
        self.workspace_dropdown.bind("<<ComboboxSelected>>", self._on_workspace_selected)

        # --- LEFT COLUMN: ROM Information Card ---
        self.info_card = ttk.Frame(left_col, style="Card.TFrame", padding=15)
        self.info_card.pack(fill="both", expand=True, pady=(0, 10))

        ttk.Label(self.info_card, text="Target ROM Metadata", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))

        self.info_text_var = tk.StringVar(value="No ROM loaded.\nSelect a file above or pick a homebrew test ROM.")
        self.info_lbl = ttk.Label(self.info_card, textvariable=self.info_text_var, style="CardBody.TLabel", justify="left", wraplength=340)
        self.info_lbl.pack(anchor="nw", fill="both", expand=True)

        # --- LEFT COLUMN: Action Controls ---
        action_card = ttk.Frame(left_col, style="Card.TFrame", padding=15)
        action_card.pack(fill="x")

        self.recompile_btn = ttk.Button(action_card, text="Recompile ROM to Native .EXE", style="Primary.TButton", command=self._start_recompile)
        self.recompile_btn.pack(fill="x", pady=(0, 6))

        self.blocks_btn = ttk.Button(action_card, text="Inspect Blocks & Entropy Map", style="Action.TButton", command=self._start_inspect_blocks)
        self.blocks_btn.pack(fill="x", pady=(0, 6))

        self.window_mode_var = tk.BooleanVar(value=True)
        self.window_chk = tk.Checkbutton(
            action_card,
            text="Launch with Desktop Display Window (--window)",
            variable=self.window_mode_var,
            bg=self.colors["bg_card"],
            fg=self.colors["text"],
            selectcolor=self.colors["bg_surface"],
            activebackground=self.colors["bg_card"],
            activeforeground=self.colors["accent"]
        )
        self.window_chk.pack(anchor="w", pady=(0, 8))

        self.play_btn = ttk.Button(action_card, text="Run Recompiled Game", style="Play.TButton", state="disabled", command=self._launch_game)
        self.play_btn.pack(fill="x")

        # --- RIGHT COLUMN: Execution Console & Progress ---
        console_card = ttk.Frame(right_col, style="Card.TFrame", padding=15)
        console_card.pack(fill="both", expand=True)

        console_header = ttk.Frame(console_card, style="Card.TFrame")
        console_header.pack(fill="x", pady=(0, 8))

        ttk.Label(console_header, text="Recompilation Console & Build Output", style="CardTitle.TLabel").pack(side="left")

        clear_btn = ttk.Button(console_header, text="Clear", style="Action.TButton", command=self._clear_console)
        clear_btn.pack(side="right")

        self.progress_bar = ttk.Progressbar(console_card, mode="indeterminate")
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

        # Scrollbar
        scroll = ttk.Scrollbar(self.console_text, command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        self._log("=== Automated Game ROM Recompiler Framework Ready ===")
        self._log("Ready to ingest Game Boy Advance, Nintendo 64, and PS1 ROMs.\n")

    def _log(self, text: str):
        self.console_text.insert("end", text + "\n")
        self.console_text.see("end")

    def _clear_console(self):
        self.console_text.delete("1.0", "end")

    def _scan_workspace_roms(self):
        rom_dir = "roms"
        discovered = []
        if os.path.exists(rom_dir):
            for root, _, files in os.walk(rom_dir):
                for f in files:
                    if f.endswith((".gba", ".z64", ".n64", ".v64", ".bin", ".exe", ".iso")) and not f.startswith("."):
                        rel_path = os.path.relpath(os.path.join(root, f), ".")
                        discovered.append(rel_path)

        if discovered:
            self.workspace_dropdown["values"] = discovered
            # Select test ROM by default if present
            test_rom = "roms\\test\\hello_gba.gba" if os.name == "nt" else "roms/test/hello_gba.gba"
            for item in discovered:
                if "hello_gba.gba" in item:
                    self.workspace_roms_var.set(item)
                    self._load_rom(item)
                    break

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
        if os.path.isfile(exe_cand):
            self.recompiled_exe_path = exe_cand
            self.play_btn.config(state="normal", text=f"Run {os.path.basename(exe_cand)}")
        else:
            self.play_btn.config(state="disabled", text="Run Recompiled Game")

        self._log(f"-> Loaded ROM: {os.path.basename(rom_path)} [{info.get('console')}]")

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

            # Print blocks into log
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
                self._log("  [2/4] Recursive Control Flow Graph Disassembly (ARM)")
                self._log("========================================================")
                self._log("Traversing reachable basic blocks from 0x08000000...")
                c_code = lift_rom_to_c(rom_path, entry_point=0x08000000, max_blocks=1500)
            elif "Nintendo 64" in console or "PlayStation 1" in console:
                self._log("\n========================================================")
                self._log("  [2/4] Recursive Control Flow Graph Disassembly (MIPS)")
                self._log("========================================================")
                raw_ep = info.get("entry_point")
                ep = int(raw_ep, 16) if isinstance(raw_ep, str) and raw_ep.startswith("0x") else None
                self._log(f"Traversing reachable MIPS blocks from {raw_ep}...")
                c_code = lift_mips_rom_to_c(rom_path, entry_point=ep, max_blocks=1500)
            else:
                self._log(f"Console '{console}' lifter is not yet automated.")
                return

            self._log("\n========================================================")
            self._log("  [3/4] Emitting Native C Source Code")
            self._log("========================================================")
            with open(out_c_path, "w") as f:
                f.write(c_code)
            self._log(f"Saved: {out_c_path} ({len(c_code.splitlines())} lines)")

            # Stage 4: Compile to Native Executable
            self._log("\n========================================================")
            self._log("  [4/4] Native Compiler Driver (MSVC / Clang / GCC)")
            self._log("========================================================")
            success = compile_c_to_exe(out_c_path, out_exe_path)

            if success and os.path.isfile(out_exe_path):
                self.recompiled_exe_path = out_exe_path
                self.play_btn.config(state="normal", text=f"Run {os.path.basename(out_exe_path)}")
                self._log("\n========================================================")
                self._log(f"  SUCCESS: Standalone Binary Built: {out_exe_path}")
                self._log("========================================================")
                self._log("Click 'Run Recompiled Game' to test execution directly!\n")
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
            # Launch in independent process
            subprocess.Popen(cmd)
        except Exception as e:
            messagebox.showerror("Execution Error", f"Failed to launch executable:\n{e}")

    def _set_busy(self, busy: bool):
        self.is_busy = busy
        if busy:
            self.progress_bar.start(10)
            self.recompile_btn.config(state="disabled")
            self.blocks_btn.config(state="disabled")
        else:
            self.progress_bar.stop()
            self.recompile_btn.config(state="normal")
            self.blocks_btn.config(state="normal")


def main():
    app = RecompilerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
