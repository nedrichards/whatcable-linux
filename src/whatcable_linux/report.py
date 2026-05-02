from __future__ import annotations

from pathlib import Path

from .advanced_sources import scan_advanced_sources
from .models import SystemReport
from .sysfs import scan as scan_typec
from .usb_sysfs import scan_usb_devices


def scan_system(
    typec_root: Path | str = "/sys/class/typec",
    pd_root: Path | str = "/sys/class/usb_power_delivery",
    usb_root: Path | str = "/sys/bus/usb/devices",
    thunderbolt_root: Path | str = "/sys/bus/thunderbolt/devices",
    usb4_root: Path | str = "/sys/bus/usb4/devices",
    debug_usb_devices: Path | str = "/sys/kernel/debug/usb/devices",
) -> SystemReport:
    return SystemReport(
        typec_ports=scan_typec(typec_root, pd_root),
        usb_devices=scan_usb_devices(usb_root),
        advanced_devices=scan_advanced_sources(thunderbolt_root, usb4_root, debug_usb_devices),
    )
