from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .advanced_sources import scan_advanced_sources
from .chrome_ec import scan_chrome_ec
from .models import SystemReport
from .sysfs import scan as scan_typec
from .usb_sysfs import scan_usb_devices
from .ucsi import scan_ucsi
from .usb4_debug import scan_usb4_debug


def scan_system(
    typec_root: Path | str = "/sys/class/typec",
    pd_root: Path | str = "/sys/class/usb_power_delivery",
    usb_root: Path | str = "/sys/bus/usb/devices",
    thunderbolt_root: Path | str = "/sys/bus/thunderbolt/devices",
    usb4_root: Path | str = "/sys/bus/usb4/devices",
    debug_usb_devices: Path | str = "/sys/kernel/debug/usb/devices",
    chrome_ec_root: Path | str = "/sys/class/chromeos/cros_ec",
    chrome_ec_device: Path | str = "/dev/cros_ec",
    acpi_root: Path | str = "/sys/bus/acpi/devices",
    usb4_debug: bool = False,
    usb4_debug_root: Path | str = "/sys/kernel/debug/thunderbolt",
) -> SystemReport:
    advanced_devices = scan_advanced_sources(thunderbolt_root, usb4_root, debug_usb_devices)
    advanced_devices.extend(scan_chrome_ec(chrome_ec_root, chrome_ec_device))
    ports = scan_typec(typec_root, pd_root)
    usb_devices = scan_usb_devices(usb_root)
    advanced_devices.extend(scan_ucsi(acpi_root, ports))
    if usb4_debug:
        advanced_devices.extend(scan_usb4_debug(usb4_debug_root))
    for index, device in enumerate(advanced_devices):
        if device.negotiated_link and device.sysfs_path:
            router = Path(device.sysfs_path)
            related = []
            for usb in usb_devices:
                link = Path(usb.sysfs_path) / "usb4_port"
                try:
                    if link.is_symlink() and link.resolve(strict=True).is_relative_to(router):
                        related.append(usb.name)
                except OSError:
                    pass
            advanced_devices[index] = replace(device, negotiated_link=replace(
                device.negotiated_link, usb_devices=related))
    return SystemReport(
        typec_ports=ports,
        usb_devices=usb_devices,
        advanced_devices=advanced_devices,
    )
