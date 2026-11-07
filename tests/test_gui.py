import os
import queue
import subprocess
import threading
from types import SimpleNamespace

import pytest

import gui
from gui import RecompilerGUI


class Widget:
    """A small Tk substitute that rejects access from a worker thread."""

    def __init__(self, value=None):
        self.value = value
        self.options = {}
        self.text = ""
        self.owner = threading.current_thread()
        self.items = {}

    def _check_thread(self):
        assert threading.current_thread() is self.owner

    def config(self, **options):
        self._check_thread()
        self.options.update(options)

    def get(self, *args):
        self._check_thread()
        return self.text if args else self.value

    def set(self, value):
        self._check_thread()
        self.value = value

    def insert(self, index, text, *tags):
        self._check_thread()
        self.text += text

    def delete(self, first, last):
        self._check_thread()
        if last == "1001.0":
            self.text = "\n".join(self.text.split("\n")[1000:])
        else:
            self.text = ""

    def index(self, index):
        self._check_thread()
        return f"{len(self.text.splitlines())}.0"

    def see(self, index):
        self._check_thread()

    def search(self, *args, **kwargs):
        self._check_thread()
        return ""

    def start(self, interval):
        self.config(running=True)

    def stop(self):
        self.config(running=False)

    def create_image(self, *coords, **options):
        self._check_thread()
        item = len(self.items) + 1
        self.items[item] = options
        return item

    def itemconfigure(self, item, **options):
        self._check_thread()
        self.items[item].update(options)


class HeadlessGUI:
    def __init__(self):
        self._closed = False
        self._ui_thread = threading.current_thread()
        self._ui_events = queue.Queue(maxsize=1000)
        self._ui_poll_id = None
        self.scheduled = {}
        self._preview_reader = None
        self._preview_reader_path = None
        self._viewport_image_item = None
        self.viewport_image_ref = None
        self.current_rom_path = None
        self.current_rom_info = None
        self.recompiled_exe_path = None
        self.recompiled_c_path = None
        self.is_busy = False
        for name in ("console_text", "source_text", "info_text_var", "viewport_canvas",
                     "viewport_status_var", "play_btn", "vp_launch_btn", "vp_snapshot_btn",
                     "status_pill", "progress_bar", "recompile_btn", "blocks_btn"):
            setattr(self, name, Widget())
        self.max_blocks_var = Widget(100)
        self.no_build_var = Widget(False)

    def __getattr__(self, name):
        method = getattr(RecompilerGUI, name)
        return method.__get__(self, type(self))

    def after(self, delay, callback):
        assert threading.current_thread() is self._ui_thread
        token = f"callback-{len(self.scheduled) + 1}"
        self.scheduled[token] = callback
        return token

    def after_cancel(self, token):
        assert threading.current_thread() is self._ui_thread
        self.scheduled.pop(token, None)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(gui.ImageTk, "PhotoImage", lambda image: image.copy())
    return HeadlessGUI()


def run_worker(callback):
    errors = []

    def run():
        try:
            callback()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert not errors


def gba_info(path):
    return {"console": "Game Boy Advance (GBA)", "title": "Homebrew",
            "filename": os.path.basename(path), "entry_point": "0x08000000", "size_bytes": 1024}


def test_rom_preview_reuses_canvas_and_reader(app, tmp_path, monkeypatch):
    rom = tmp_path / "preview.gba"
    rom.write_bytes(bytes(range(256)) * 4)
    app.current_rom_path = str(rom)
    app.current_rom_info = gba_info(rom)
    readers = []
    factory = gui.create_block_reader

    def create(path):
        readers.append(factory(path))
        return readers[-1]

    monkeypatch.setattr(gui, "create_block_reader", create)
    for _ in range(120):
        app._render_viewport_frame()
    assert len(app.viewport_canvas.items) == 1
    assert len(readers) == 1
    assert "ROM data preview" in app.viewport_status_var.get()
    assert "Execution" not in app.viewport_status_var.get()
    app._shutdown()


def test_switching_rom_clears_previous_build_and_closes_reader(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.mkdir("build")
    first = tmp_path / "first.gba"
    second = tmp_path / "second.gba"
    first.write_bytes(b"\x00" * 1024)
    second.write_bytes(b"\x00" * 1024)
    (tmp_path / "build" / "first.exe").write_bytes(b"binary")
    (tmp_path / "build" / "first_recompiled.c").write_text("first source")
    monkeypatch.setattr(gui, "inspect_file", gba_info)
    app._refresh_entropy_canvas = lambda: None
    app._load_rom(str(first))
    old_reader = app._preview_reader
    closed = []
    original_close = old_reader.close
    old_reader.close = lambda: (closed.append(True), original_close())
    assert app.recompiled_exe_path is not None
    assert "first source" in app.source_text.text
    app._load_rom(str(second))
    assert closed == [True]
    assert app.recompiled_exe_path is None
    assert app.recompiled_c_path is None
    assert "first source" not in app.source_text.text
    assert app.play_btn.options["state"] == "disabled"
    assert app.vp_snapshot_btn.options["state"] == "disabled"
    app._shutdown()


def test_worker_logs_and_busy_updates_touch_tk_only_when_drained(app):
    run_worker(lambda: (app._log("worker output"), app._set_busy(True)))
    assert app.console_text.text == ""
    assert not app.is_busy
    app._drain_ui_events()
    assert "worker output" in app.console_text.text
    assert app.is_busy
    assert app.progress_bar.options["running"] is True
    assert app.recompile_btn.options["state"] == "disabled"


def test_shutdown_cancels_callbacks_and_discards_late_worker_updates(app):
    closed = []
    app._preview_reader = SimpleNamespace(close=lambda: closed.append(True))
    app._ui_poll_id = app.after(25, app._drain_ui_events)
    run_worker(lambda: app._log("queued before shutdown"))
    app._shutdown()
    run_worker(lambda: (app._log("late output"), app._set_busy(False)))
    app._drain_ui_events()
    assert closed == [True]
    assert not app.scheduled
    assert app._ui_events.empty()
    assert app.console_text.text == ""


def test_failed_ui_callback_does_not_stop_remaining_updates(app):
    def fail():
        raise ValueError("invalid update")

    run_worker(lambda: (app._dispatch_ui(fail), app._log("next update")))
    app._drain_ui_events()
    assert "Interface update failed: invalid update" in app.console_text.text
    assert "next update" in app.console_text.text
    assert app._ui_poll_id is not None


def test_console_output_is_pruned(app):
    app._log("\n".join(f"line {i}" for i in range(5100)))
    assert len(app.console_text.text.splitlines()) <= 5000
    assert "line 5099" in app.console_text.text


def test_build_settings_are_read_before_worker_starts(app, monkeypatch):
    app.current_rom_path = "original.gba"
    app.current_rom_info = gba_info("original.gba")
    calls = []

    class Thread:
        def __init__(self, target, args, daemon):
            calls.append((target, args, daemon))

        def start(self):
            pass

    monkeypatch.setattr(gui.threading, "Thread", Thread)
    app._start_recompile()
    app.current_rom_path = "different.gba"
    app.max_blocks_var.value = 200
    target, args, daemon = calls[0]
    assert args == ("original.gba", gba_info("original.gba"), 100, False)
    assert daemon
    assert target.__name__ == "_run_recompile_thread"


def test_invalid_build_setting_does_not_start_worker(app, monkeypatch):
    app.current_rom_path = "homebrew.gba"
    app.max_blocks_var.value = 0
    warnings = []
    monkeypatch.setattr(gui.messagebox, "showwarning", lambda *args: warnings.append(args))
    app._start_recompile()
    assert not app.is_busy
    assert warnings[0][0] == "Invalid Build Settings"


def test_inspection_error_clears_previous_rom_state(app, monkeypatch):
    app.current_rom_path = "previous.gba"
    app.recompiled_exe_path = "previous.exe"
    app.recompiled_c_path = "previous.c"

    def inspect(path):
        raise OSError("file disappeared")

    monkeypatch.setattr(gui, "inspect_file", inspect)
    app._load_rom("missing.gba")
    assert app.current_rom_info is None
    assert app.recompiled_exe_path is None
    assert app.recompiled_c_path is None
    assert "file disappeared" in app.console_text.text
    assert "could not be inspected" in app.viewport_status_var.get()


def test_worker_compile_failure_keeps_source_and_restores_controls(app, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app.current_rom_path = "homebrew.gba"
    app.current_rom_info = gba_info(app.current_rom_path)
    app.is_busy = True
    monkeypatch.setattr(gui, "lift_rom_to_c", lambda *args, **kwargs: "int main(void) { return 0; }")
    monkeypatch.setattr(gui, "compile_c_to_exe", lambda *args, **kwargs: False)
    run_worker(lambda: app._run_recompile_thread(app.current_rom_path, dict(app.current_rom_info), 100, False))
    app._drain_ui_events()
    assert not app.is_busy
    assert app.recompiled_exe_path is None
    assert app.recompiled_c_path == os.path.join("build", "homebrew_recompiled.c")
    assert "int main" in app.source_text.text
    assert "Native compilation failed" in app.console_text.text
    assert app.play_btn.options["state"] == "disabled"


def test_old_build_results_do_not_replace_selected_rom(app):
    app.current_rom_path = "selected.gba"
    app._publish_build_result("old.gba", "old.c", "old.exe")
    assert app.recompiled_c_path is None
    assert app.recompiled_exe_path is None


def test_native_snapshot_displays_native_pixels_and_cleans_temp_file(app, monkeypatch):
    app.current_rom_path = "homebrew.gba"
    app.current_rom_info = gba_info(app.current_rom_path)
    app.is_busy = True
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        gui.Image.new("RGB", (240, 160), (248, 0, 0)).save(command[-1], format="PPM")
        return SimpleNamespace(returncode=0, stderr="", stdout="complete")

    monkeypatch.setattr(gui.subprocess, "run", run)
    run_worker(lambda: app._run_framebuffer_snapshot("homebrew.gba", "game.exe"))
    assert app.viewport_image_ref is None
    app._drain_ui_events()
    assert app.viewport_image_ref.getpixel((360, 240)) == (248, 0, 0)
    assert "Native GBA framebuffer snapshot" in app.viewport_status_var.get()
    assert not app.is_busy
    command, options = calls[0]
    assert command[:3] == ["game.exe", "--headless", "--framebuffer"]
    assert options["timeout"] == 15
    if gui.sys.platform == "win32":
        assert options["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert not os.path.exists(command[-1])


@pytest.mark.parametrize("failure", ["exit", "timeout", "missing", "dimensions"])
def test_native_snapshot_failures_restore_gui_without_fake_frame(app, monkeypatch, failure):
    app.current_rom_path = "homebrew.gba"
    app.is_busy = True

    def run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 15)
        if failure == "exit":
            return SimpleNamespace(returncode=2, stderr="unsupported option", stdout="")
        if failure == "dimensions":
            gui.Image.new("RGB", (1, 1)).save(command[-1], format="PPM")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(gui.subprocess, "run", run)
    run_worker(lambda: app._run_framebuffer_snapshot("homebrew.gba", "game.exe"))
    app._drain_ui_events()
    assert not app.is_busy
    assert app.viewport_image_ref is None
    assert "snapshot failed" in app.viewport_status_var.get()
    assert "[Error]" in app.console_text.text
