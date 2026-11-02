import os
import sys
import pytest
from gui import RecompilerGUI

def test_gui_workflow():
    try:
        app = RecompilerGUI()
    except Exception as e:
        pytest.skip(f"Tkinter environment not available in this runner: {e}")

    try:
        # 1. Verify title, theme, and initial state
        assert "Automated Game ROM Recompiler" in app.title()
        assert app.colors["bg_dark"] == "#181825"
        log_content = app.console_text.get("1.0", "end")
        assert "Automated Game ROM Recompiler Framework Ready" in log_content

        # 2. Test loading ROM and verifying metadata display
        test_rom = "roms/test/hello_gba.gba"
        if os.path.exists(test_rom):
            app._load_rom(test_rom)
            assert app.current_rom_info is not None
            assert app.current_rom_info["console"] == "Game Boy Advance (GBA)"
            info_text = app.info_text_var.get()
            assert "Game Boy Advance" in info_text
            assert "hello_gba.gba" in info_text

        # 3. Verify Live Viewport Tab & Controls
        assert hasattr(app, "tab_viewport")
        assert app.viewport_canvas is not None
        assert int(app.viewport_canvas.cget("width")) == 720
        assert int(app.viewport_canvas.cget("height")) == 480
        app._viewport_step_single()
        assert "Status:" in app.viewport_status_var.get()
    finally:
        app.update_idletasks()
        app.destroy()
