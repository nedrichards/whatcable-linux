"""Exercise installed native widgets with isolated fixture data and save review captures."""

# ruff: noqa: E402 -- GI versions must be selected before repository imports.
import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk


def installed(module):
    if not Path(module.__file__).resolve().is_relative_to("/app"):
        raise RuntimeError("Smoke imported checkout code instead of the installed package")


def pump(ready, seconds=5):
    deadline = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if ready():
            return
        time.sleep(0.01)
    raise RuntimeError("Native window did not settle before the capture deadline")


WIDTHS = (480, 1100)


def create(stack):
    import whatcable_linux.app as module
    from whatcable_linux.models import SystemReport

    installed(module)
    report = SystemReport()
    stack.enter_context(patch.object(module, "scan_system", return_value=report))
    stack.enter_context(patch.object(module.WhatCableApplication, "_watch_sysfs"))
    app = module.WhatCableApplication()
    app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
    if not app.register(None):
        raise RuntimeError("Could not register fixture application")
    app.activate()
    return app, app.window, lambda: not app.scan_running and app.last_report == report



def capture_node(window):
    nodes = []
    allocations = []
    frames = []

    def rendered():
        frame = window.get_frame_clock().get_frame_counter()
        if not frames or frame != frames[-1]:
            frames.append(frame)
            allocations.append((window.get_width(), window.get_height()))
        if len(allocations) < 3 or len(set(allocations[-3:])) != 1:
            window.queue_draw()
            return False
        snapshot = Gtk.Snapshot.new()
        Gtk.WidgetPaintable.new(window).snapshot(snapshot, window.get_width(), window.get_height())
        node = snapshot.to_node()
        if node is None:
            window.queue_draw()
            return False
        nodes.append(node)
        return True

    pump(rendered)
    return nodes[0]


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        raise RuntimeError("Installed visual smoke requires a native display")
    Adw.init()
    settings = Gtk.Settings.get_default()
    settings.set_property("gtk-enable-animations", False)
    if os.getenv("CI_LARGE_TEXT") == "1":
        settings.set_property("gtk-font-name", "Adwaita Sans 16")
    manager = Adw.StyleManager.get_default()
    if os.getenv("ADW_DEBUG_HIGH_CONTRAST") == "1" and not manager.get_high_contrast():
        raise RuntimeError("Requested high contrast is not active")
    errors = []
    def record_error(*error):
        errors.append(error)
        sys.__excepthook__(*error)

    sys.excepthook = record_error
    with ExitStack() as stack:
        app, window, ready = create(stack)
        try:
            for scheme, label in ((Adw.ColorScheme.FORCE_LIGHT, "light"), (Adw.ColorScheme.FORCE_DARK, "dark")):
                manager.set_color_scheme(scheme)
                for width in WIDTHS:
                    window.set_default_size(width, 780)
                    window.present()
                    pump(lambda: window.get_mapped() and ready())
                    clock = window.get_frame_clock()
                    frame = clock.get_frame_counter()
                    window.queue_draw()
                    pump(lambda clock=clock, frame=frame: clock.get_frame_counter() > frame)
                    if errors:
                        raise RuntimeError(f"Native callback failed: {errors}")
                    node = capture_node(window)
                    texture = window.get_renderer().render_texture(node, None)
                    target = output / f"window-{width}-{label}.png"
                    if not texture.save_to_png(str(target)):
                        raise RuntimeError("Could not save native fixture capture")
                    print(f"CAPTURE_PASS: {target.name} requested={width} allocated={window.get_width()}x{window.get_height()}", flush=True)
        finally:
            window.destroy()
            app.quit()
    print("INSTALLED_VISUAL_SMOKE_PASS", flush=True)


if __name__ == "__main__":
    main()
