from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import __version__
from .report import scan_system
from .summary import summarize_port
from .naming import usb_class_label
from .usb_sysfs import is_root_hub, summarize_usb_device, usb_device_bullets, usb_device_name

APP_ID = "com.nedrichards.WhatCable"


class WhatCableApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window: Adw.ApplicationWindow | None = None
        self.port_list: Gtk.ListBox | None = None
        self.details: Gtk.Box | None = None
        self.status_label: Gtk.Label | None = None
        self.raw_button: Gtk.ToggleButton | None = None
        self.show_raw = False
        self.selected_kind: str | None = None
        self.selected_item = None
        self.monitors: list[Gio.FileMonitor] = []
        self.refresh_source_id: int | None = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self._load_css()

        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", lambda *_args: self.refresh())
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["<primary>r", "F5"])

        raw_action = Gio.SimpleAction.new_stateful("raw", None, GLib.Variant.new_boolean(False))
        raw_action.connect("activate", self._toggle_raw)
        self.add_action(raw_action)
        self.set_accels_for_action("app.raw", ["<primary>i"])

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_args: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_activate(self) -> None:
        if self.window is None:
            self.window = self._build_window()
            self._watch_sysfs()
        self.window.present()
        self.refresh()

    def refresh(self) -> None:
        report = scan_system()
        usb_devices = [device for device in report.usb_devices if not is_root_hub(device)]
        total_items = len(report.typec_ports) + len(usb_devices) + len(report.advanced_devices)
        if self.status_label is not None:
            if total_items:
                self.status_label.set_label(f"{total_items} devices")
                self.status_label.set_tooltip_text(
                    f"{len(report.typec_ports)} USB-C ports\n"
                    f"{len(usb_devices)} USB devices\n"
                    f"{len(report.advanced_devices)} advanced sources"
                )
            else:
                self.status_label.set_label("No devices")
                self.status_label.set_tooltip_text(None)

        if self.port_list is None or self.details is None:
            return

        _clear_listbox(self.port_list)
        _clear_box(self.details)

        if not report.typec_ports and not usb_devices and not report.advanced_devices:
            self.selected_kind = None
            self.selected_item = None
            self.details.append(_empty_state())
            return

        target_kind, target_key = self._selected_key()
        first_item: tuple[str, object] | None = None
        shown_selection = False

        if report.typec_ports:
            self.port_list.append(_section_label("USB-C Ports"))
        for port in report.typec_ports:
            summary = summarize_port(port)
            row = Adw.ActionRow(title=port.name, subtitle=summary.headline)
            row.add_prefix(_status_dot(summary.status))
            row.set_activatable(True)
            row.connect("activated", lambda _row, selected=port: self._show_port(selected))
            self.port_list.append(row)
            if first_item is None:
                first_item = ("typec", port)
            if target_kind == "typec" and target_key == port.name:
                self._show_port(port)
                shown_selection = True

        if usb_devices:
            self.port_list.append(_section_label("USB Devices"))
        for device in usb_devices:
            title = usb_device_name(device)
            row = Adw.ActionRow(title=title, subtitle=summarize_usb_device(device))
            row.add_prefix(_status_dot("usb"))
            row.set_activatable(True)
            row.connect("activated", lambda _row, selected=device: self._show_usb_device(selected))
            self.port_list.append(row)
            if first_item is None:
                first_item = ("usb", device)
            if target_kind == "usb" and target_key == device.name:
                self._show_usb_device(device)
                shown_selection = True

        if report.advanced_devices:
            self.port_list.append(_section_label("Advanced Sources"))
        for device in report.advanced_devices:
            row = Adw.ActionRow(title=device.name, subtitle=f"{device.source} · {device.summary or device.name}")
            row.add_prefix(_status_dot("advanced"))
            row.set_activatable(True)
            row.connect("activated", lambda _row, selected=device: self._show_advanced_device(selected))
            self.port_list.append(row)
            if first_item is None:
                first_item = ("advanced", device)
            if target_kind == "advanced" and target_key == f"{device.source}:{device.name}":
                self._show_advanced_device(device)
                shown_selection = True

        if not shown_selection and first_item is not None:
            kind, item = first_item
            if kind == "typec":
                self._show_port(item)
            elif kind == "usb":
                self._show_usb_device(item)
            else:
                self._show_advanced_device(item)

    def _show_port(self, port) -> None:
        if self.details is None:
            return

        self.selected_kind = "typec"
        self.selected_item = port
        _clear_box(self.details)
        summary = summarize_port(port)

        chips = [
            value
            for value in (
                port.port_type,
                f"Power {port.power_role}" if port.power_role else None,
                f"Data {port.data_role}" if port.data_role else None,
                f"PD {port.usb_power_delivery_revision}" if port.usb_power_delivery_revision else None,
            )
            if value
        ]
        self.details.append(_hero("drive-removable-media-symbolic", summary.status, summary.headline, summary.subtitle, chips))

        metrics = [
            ("Power role", port.power_role or "Unknown"),
            ("Data role", port.data_role or "Unknown"),
            ("Port type", port.port_type or "Unknown"),
            ("PD revision", port.usb_power_delivery_revision or "Not exposed"),
        ]
        self.details.append(_metric_grid(metrics))

        facts = Adw.PreferencesGroup(title="Capabilities")
        facts.add(_row("Port", port.name, icon="input-dialpad-symbolic"))
        for bullet in summary.bullets:
            facts.add(_row("Capability", bullet, icon="dialog-information-symbolic"))
        self.details.append(facts)

        if port.partner:
            partner = Adw.PreferencesGroup(title="Partner")
            partner.add(_row("Name", port.partner.name, icon="computer-symbolic"))
            if port.partner.supports_usb_power_delivery is not None:
                partner.add(_row("Power Delivery", "Yes" if port.partner.supports_usb_power_delivery else "No"))
            for mode in port.partner.alt_modes:
                partner.add(_row("Alt mode", mode))
            self.details.append(partner)

        if port.cable:
            cable = Adw.PreferencesGroup(title="Cable")
            cable.add(_row("Name", port.cable.name, icon="drive-removable-media-symbolic"))
            if port.cable.active is not None:
                cable.add(_row("Type", "Active" if port.cable.active else "Passive"))
            if port.cable.identity:
                cable.add(_row("Identity", "Exposed by kernel"))
            self.details.append(cable)

        if self.show_raw:
            self.details.append(_raw_group(dataclasses.asdict(port)))

    def _show_usb_device(self, device) -> None:
        if self.details is None:
            return

        self.selected_kind = "usb"
        self.selected_item = device
        _clear_box(self.details)

        title = usb_device_name(device)
        subtitle = summarize_usb_device(device)
        chips = [
            value
            for value in (
                f"{device.id_vendor}:{device.id_product}" if device.id_vendor and device.id_product else None,
                f"Bus {device.busnum}" if device.busnum else None,
                f"Device {device.devnum}" if device.devnum else None,
                device.driver,
            )
            if value
        ]
        self.details.append(_hero("drive-harddisk-symbolic", "usb", title, subtitle, chips))

        metrics = [
            ("Speed", _speed_label(device.speed) if device.speed else "Unknown"),
            ("USB", device.version or "Unknown"),
            ("Power", device.max_power or "Not exposed"),
            ("Interfaces", str(len(device.interfaces))),
        ]
        self.details.append(_metric_grid(metrics))

        facts = Adw.PreferencesGroup(title="Details")
        facts.add(_row("Device", device.name, icon="drive-harddisk-symbolic"))
        for bullet in usb_device_bullets(device):
            facts.add(_row("Property", bullet, icon="dialog-information-symbolic"))
        self.details.append(facts)

        if device.interfaces:
            interfaces = Adw.PreferencesGroup(title="Interfaces")
            for interface in device.interfaces:
                bits = []
                if interface.interface_number:
                    bits.append(f"number {interface.interface_number}")
                if interface.interface_class:
                    class_label = usb_class_label(interface.interface_class)
                    bits.append(
                        "class "
                        + ":".join(
                            part
                            for part in (
                                interface.interface_class,
                                interface.interface_subclass,
                                interface.interface_protocol,
                            )
                            if part is not None
                        )
                        + (f" · {class_label}" if class_label else "")
                    )
                if interface.driver:
                    bits.append(f"driver {interface.driver}")
                interfaces.add(_row(interface.name, ", ".join(bits) or "No details exposed", icon="network-wired-symbolic"))
            self.details.append(interfaces)

        if self.show_raw:
            self.details.append(_raw_group(dataclasses.asdict(device)))

    def _show_advanced_device(self, device) -> None:
        if self.details is None:
            return

        self.selected_kind = "advanced"
        self.selected_item = device
        _clear_box(self.details)

        chips = [device.source]
        if device.sysfs_path:
            chips.append(Path(device.sysfs_path).name)
        self.details.append(_hero("applications-system-symbolic", "advanced", device.name, device.summary or device.source, chips))

        properties = Adw.PreferencesGroup(title="Properties")
        if device.sysfs_path:
            properties.add(_row("Path", device.sysfs_path, icon="folder-symbolic"))
        for key, value in device.properties.items():
            properties.add(_row(key.replace("_", " ").title(), value, icon="dialog-information-symbolic"))
        self.details.append(properties)

        if self.show_raw:
            self.details.append(_raw_group(dataclasses.asdict(device)))

    def _build_window(self) -> Adw.ApplicationWindow:
        window = Adw.ApplicationWindow(application=self, title="WhatCable")
        window.set_default_size(900, 620)

        toolbar = Adw.HeaderBar()
        toolbar.set_title_widget(Adw.WindowTitle(title="Devices", subtitle=""))
        refresh_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_button.set_tooltip_text("Refresh")
        refresh_button.set_action_name("app.refresh")
        toolbar.pack_start(refresh_button)

        self.status_label = Gtk.Label(label="0 ports")
        self.status_label.add_css_class("dim-label")
        toolbar.pack_end(self.status_label)

        split = Adw.NavigationSplitView()
        split.set_min_sidebar_width(300)
        split.set_max_sidebar_width(420)

        sidebar_page = Adw.NavigationPage(title="Ports")
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.append(toolbar)
        self.port_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.port_list.add_css_class("navigation-sidebar")
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(self.port_list)
        sidebar_box.append(scroller)
        sidebar_page.set_child(sidebar_box)

        content_page = Adw.NavigationPage(title="WhatCable")
        content_toolbar = Adw.HeaderBar()
        content_toolbar.set_title_widget(Adw.WindowTitle(title="WhatCable", subtitle=""))
        self.raw_button = Gtk.ToggleButton()
        self.raw_button.set_icon_name("document-properties-symbolic")
        self.raw_button.set_tooltip_text("Show raw sysfs")
        self.raw_button.set_action_name("app.raw")
        content_toolbar.pack_end(self.raw_button)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(content_toolbar)
        clamp = Adw.Clamp(maximum_size=900, tightening_threshold=560)
        self.details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.details.set_margin_top(24)
        self.details.set_margin_bottom(24)
        self.details.set_margin_start(18)
        self.details.set_margin_end(18)
        clamp.set_child(self.details)
        details_scroller = Gtk.ScrolledWindow()
        details_scroller.set_vexpand(True)
        details_scroller.set_child(clamp)
        content.append(details_scroller)
        content_page.set_child(content)

        split.set_sidebar(sidebar_page)
        split.set_content(content_page)
        window.set_content(split)
        return window

    def _toggle_raw(self, action: Gio.SimpleAction, _parameter) -> None:
        self.show_raw = not action.get_state().get_boolean()
        action.set_state(GLib.Variant.new_boolean(self.show_raw))
        if self.raw_button is not None:
            self.raw_button.set_active(self.show_raw)
        if self.selected_kind == "typec" and self.selected_item is not None:
            self._show_port(self.selected_item)
        elif self.selected_kind == "usb" and self.selected_item is not None:
            self._show_usb_device(self.selected_item)
        elif self.selected_kind == "advanced" and self.selected_item is not None:
            self._show_advanced_device(self.selected_item)

    def _watch_sysfs(self) -> None:
        for path in (
            "/sys/class/typec",
            "/sys/class/usb_power_delivery",
            "/sys/bus/usb/devices",
            "/sys/bus/thunderbolt/devices",
            "/sys/bus/usb4/devices",
        ):
            file = Gio.File.new_for_path(path)
            if not file.query_exists(None):
                continue
            try:
                monitor = file.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            except GLib.Error:
                continue
            monitor.connect("changed", self._sysfs_changed)
            self.monitors.append(monitor)

        GLib.timeout_add_seconds(5, self._poll_sysfs)

    def _sysfs_changed(self, *_args) -> None:
        self._schedule_refresh()

    def _poll_sysfs(self) -> bool:
        self._schedule_refresh()
        return True

    def _schedule_refresh(self) -> None:
        if self.refresh_source_id is not None:
            return
        self.refresh_source_id = GLib.timeout_add(350, self._run_scheduled_refresh)

    def _run_scheduled_refresh(self) -> bool:
        self.refresh_source_id = None
        self.refresh()
        return False

    def _selected_key(self) -> tuple[str | None, str | None]:
        if self.selected_item is None:
            return None, None
        if self.selected_kind == "advanced":
            return self.selected_kind, f"{self.selected_item.source}:{self.selected_item.name}"
        return self.selected_kind, getattr(self.selected_item, "name", None)

    def _load_css(self) -> None:
        provider = Gtk.CssProvider()
        css_path = Path("/app/share/whatcable-linux/style.css")
        if not css_path.exists():
            css_path = Path(__file__).resolve().parents[2] / "data" / "style.css"
        try:
            provider.load_from_path(str(css_path))
        except GLib.Error:
            return
        display = Gdk.Display.get_default()
        if display is None:
            return
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def _hero(icon_name: str, status: str, title: str, subtitle: str, chips: list[str]) -> Adw.PreferencesGroup:
    group = Adw.PreferencesGroup()
    hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    hero.add_css_class("inspector-hero")

    heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
    heading.set_valign(Gtk.Align.START)
    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_pixel_size(28)
    icon.set_size_request(52, 52)
    icon.add_css_class("hero-icon")
    icon.add_css_class(f"hero-{status}")
    heading.append(icon)

    labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    labels.set_hexpand(True)
    title_label = Gtk.Label(label=title, xalign=0, wrap=True)
    title_label.add_css_class("title-2")
    subtitle_label = Gtk.Label(label=subtitle, xalign=0, wrap=True)
    subtitle_label.add_css_class("dim-label")
    labels.append(title_label)
    labels.append(subtitle_label)
    heading.append(labels)
    hero.append(heading)

    if chips:
        chip_box = Gtk.FlowBox(column_spacing=6, row_spacing=6, selection_mode=Gtk.SelectionMode.NONE)
        chip_box.add_css_class("chip-box")
        for chip in chips:
            chip_label = Gtk.Label(label=chip)
            chip_label.add_css_class("chip")
            chip_box.append(chip_label)
        hero.append(chip_box)

    group.add(hero)
    return group


def _metric_grid(metrics: list[tuple[str, str]]) -> Adw.PreferencesGroup:
    group = Adw.PreferencesGroup(title="Overview")
    for label, value in metrics:
        group.add(_row(label, value))
    return group


def _raw_group(payload: dict) -> Adw.PreferencesGroup:
    raw_group = Adw.PreferencesGroup(title="Raw sysfs")
    raw = json.dumps(payload, indent=2, sort_keys=True)
    raw_view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
    raw_view.get_buffer().set_text(raw)
    raw_view.set_vexpand(True)
    raw_view.add_css_class("raw-view")
    raw_scroller = Gtk.ScrolledWindow(min_content_height=220)
    raw_scroller.set_child(raw_view)
    raw_group.add(raw_scroller)
    return raw_group


def _row(title: str, value: str, icon: str | None = None) -> Adw.ActionRow:
    row = Adw.ActionRow(title=title, subtitle=value)
    row.set_subtitle_lines(4)
    if icon:
        image = Gtk.Image.new_from_icon_name(icon)
        image.add_css_class("dim-label")
        row.add_prefix(image)
    return row


def _status_dot(status: str) -> Gtk.Box:
    dot = Gtk.Box()
    dot.add_css_class("status-dot")
    dot.add_css_class(f"status-{status}")
    return dot


def _section_label(text: str) -> Gtk.ListBoxRow:
    row = Gtk.ListBoxRow(selectable=False, activatable=False)
    label = Gtk.Label(label=text, xalign=0)
    label.add_css_class("heading")
    label.add_css_class("section-label")
    row.set_child(label)
    return row


def _empty_state() -> Adw.StatusPage:
    page = Adw.StatusPage(
        icon_name="drive-removable-media-symbolic",
        title="No USB information exposed",
        description="This system did not report Type-C ports or USB devices through sysfs.",
    )
    return page


def _speed_label(speed: str) -> str:
    try:
        mbps = float(speed)
    except ValueError:
        return speed
    if mbps >= 1000:
        return f"{mbps / 1000:g} Gbps"
    return f"{mbps:g} Mbps"


def _clear_listbox(listbox: Gtk.ListBox) -> None:
    child = listbox.get_first_child()
    while child is not None:
        next_child = child.get_next_sibling()
        listbox.remove(child)
        child = next_child


def _clear_box(box: Gtk.Box) -> None:
    child = box.get_first_child()
    while child is not None:
        next_child = child.get_next_sibling()
        box.remove(child)
        child = next_child


def main(argv: list[str] | None = None) -> int:
    app = WhatCableApplication()
    return app.run(argv)
