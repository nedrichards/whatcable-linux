from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from . import __version__
from .report import scan_system
from .summary import summarize_port
from .usb_sysfs import is_root_hub, summarize_usb_device, usb_device_bullets


def main(argv: list[str] | None = None) -> int:
    provided_argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description="Inspect USB-C, USB device, and Power Delivery data exposed by Linux sysfs.")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--raw", action="store_true", help="include raw sysfs values")
    parser.add_argument("--typec-root", default="/sys/class/typec", help=argparse.SUPPRESS)
    parser.add_argument("--pd-root", default="/sys/class/usb_power_delivery", help=argparse.SUPPRESS)
    parser.add_argument("--usb-root", default="/sys/bus/usb/devices", help=argparse.SUPPRESS)
    parser.add_argument("--thunderbolt-root", default="/sys/bus/thunderbolt/devices", help=argparse.SUPPRESS)
    parser.add_argument("--usb4-root", default="/sys/bus/usb4/devices", help=argparse.SUPPRESS)
    parser.add_argument("--debug-usb-devices", default="/sys/kernel/debug/usb/devices", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="version", version=f"whatcable-linux {__version__}")
    parser.add_argument("--gui", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.gui or not provided_argv:
        from .app import main as app_main

        return app_main([])

    report = scan_system(
        args.typec_root,
        args.pd_root,
        args.usb_root,
        args.thunderbolt_root,
        args.usb4_root,
        args.debug_usb_devices,
    )
    usb_devices = report.usb_devices if args.raw else [
        device for device in report.usb_devices if not is_root_hub(device)
    ]
    if args.json:
        payload = {
            "typec_ports": [
                {
                    "port": dataclasses.asdict(port),
                    "summary": dataclasses.asdict(summarize_port(port)),
                }
                for port in report.typec_ports
            ],
            "usb_devices": [
                {
                    "device": dataclasses.asdict(device),
                    "summary": summarize_usb_device(device),
                    "bullets": usb_device_bullets(device),
                }
                for device in usb_devices
            ],
            "advanced_devices": [
                dataclasses.asdict(device)
                for device in report.advanced_devices
            ],
        }
        if not args.raw:
            _strip_raw(payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if not report.typec_ports and not usb_devices and not report.advanced_devices:
        print("No USB-C ports exposed by /sys/class/typec.")
        print("No USB devices exposed by /sys/bus/usb/devices.")
        print("No advanced USB4/Thunderbolt/debugfs data exposed.")
        return 0

    if report.typec_ports:
        print("USB-C ports")
        print("===========")
    for port in report.typec_ports:
        summary = summarize_port(port)
        print(f"{port.name}: {summary.headline}")
        print(f"  {summary.subtitle}")
        for bullet in summary.bullets:
            print(f"  - {bullet}")
        if args.raw:
            print(f"  raw: {port.raw}")
        print()

    if usb_devices:
        print("USB devices")
        print("===========")
    for device in usb_devices:
        print(f"{device.name}: {summarize_usb_device(device)}")
        for bullet in usb_device_bullets(device):
            print(f"  - {bullet}")
        if args.raw:
            print(f"  raw: {device.raw}")
        print()

    if report.advanced_devices:
        print("Advanced sources")
        print("================")
    for device in report.advanced_devices:
        print(f"{device.source} {device.name}: {device.summary or device.name}")
        for key, value in device.properties.items():
            print(f"  - {key}: {value}")
        if args.raw:
            print(f"  raw: {device.raw}")
        print()
    return 0


def _strip_raw(value: object) -> None:
    if isinstance(value, dict):
        value.pop("raw", None)
        for child in value.values():
            _strip_raw(child)
    elif isinstance(value, list):
        for child in value:
            _strip_raw(child)
