from __future__ import annotations

from pathlib import Path

from .models import UsbDevice, UsbInterface
from .naming import usb_class_label, usb_vendor_label

USB_DEVICE_FIELDS = (
    "busnum",
    "devnum",
    "devpath",
    "speed",
    "version",
    "idVendor",
    "idProduct",
    "manufacturer",
    "product",
    "serial",
    "bDeviceClass",
    "bDeviceSubClass",
    "bDeviceProtocol",
    "bMaxPower",
    "configuration",
    "tx_lanes",
    "rx_lanes",
)

USB_INTERFACE_FIELDS = (
    "bInterfaceClass",
    "bInterfaceSubClass",
    "bInterfaceProtocol",
    "bInterfaceNumber",
    "bAlternateSetting",
)


def scan_usb_devices(usb_root: Path | str = "/sys/bus/usb/devices") -> list[UsbDevice]:
    usb_root = Path(usb_root)
    if not usb_root.exists():
        return []

    devices: list[UsbDevice] = []
    for path in sorted(usb_root.iterdir(), key=lambda item: item.name):
        real = _safe_resolve(path)
        if not real.is_dir() or ":" in path.name:
            continue
        raw = _read_fields(real, USB_DEVICE_FIELDS)
        if not raw and not path.name.startswith("usb"):
            continue
        devices.append(
            UsbDevice(
                name=path.name,
                sysfs_path=str(real),
                busnum=raw.get("busnum"),
                devnum=raw.get("devnum"),
                devpath=raw.get("devpath"),
                speed=raw.get("speed"),
                version=raw.get("version"),
                id_vendor=raw.get("idVendor"),
                id_product=raw.get("idProduct"),
                manufacturer=raw.get("manufacturer"),
                product=raw.get("product"),
                serial=raw.get("serial"),
                device_class=raw.get("bDeviceClass"),
                device_subclass=raw.get("bDeviceSubClass"),
                device_protocol=raw.get("bDeviceProtocol"),
                max_power=raw.get("bMaxPower"),
                configuration=raw.get("configuration"),
                driver=_driver_name(real),
                tx_lanes=raw.get("tx_lanes"),
                rx_lanes=raw.get("rx_lanes"),
                interfaces=_read_interfaces(usb_root, path.name),
                raw=raw,
            )
        )
    return devices


def is_root_hub(device: UsbDevice) -> bool:
    return device.name.startswith("usb") or (
        device.id_vendor == "1d6b" and device.product and "Host Controller" in device.product
    )


def usb_device_name(device: UsbDevice) -> str:
    return (
        device.product
        or device.manufacturer
        or usb_vendor_label(device.id_vendor)
        or usb_class_label(device.device_class)
        or device.name
    )


def summarize_usb_device(device: UsbDevice) -> str:
    name = usb_device_name(device)
    bits = []
    if device.speed:
        bits.append(_speed_label(device.speed))
    if device.version:
        bits.append(f"USB {device.version}")
    if device.driver:
        bits.append(device.driver)
    return name if not bits else f"{name} · {', '.join(bits)}"


def usb_device_bullets(device: UsbDevice) -> list[str]:
    bullets: list[str] = []
    if device.id_vendor and device.id_product:
        vendor = usb_vendor_label(device.id_vendor)
        suffix = f" ({vendor})" if vendor else ""
        bullets.append(f"USB ID: {device.id_vendor}:{device.id_product}{suffix}")
    if device.manufacturer:
        bullets.append(f"Manufacturer: {device.manufacturer}")
    if device.product:
        bullets.append(f"Product: {device.product}")
    if device.speed:
        bullets.append(f"Negotiated speed: {_speed_label(device.speed)}")
    if device.version:
        bullets.append(f"USB version: {device.version}")
    if device.tx_lanes or device.rx_lanes:
        bullets.append(f"Lanes: TX {device.tx_lanes or '?'} / RX {device.rx_lanes or '?'}")
    if device.max_power:
        bullets.append(f"Max power from descriptor: {device.max_power}")
    if device.configuration:
        bullets.append(f"Configuration: {device.configuration}")
    if device.device_class:
        class_label = usb_class_label(device.device_class)
        class_code = ":".join(
            part for part in (device.device_class, device.device_subclass, device.device_protocol)
            if part is not None
        )
        bullets.append(
            "Device class: "
            + (f"{class_label} ({class_code})" if class_label else class_code)
        )
    if device.driver:
        bullets.append(f"Driver: {device.driver}")
    if device.interfaces:
        bullets.append(f"Interfaces: {len(device.interfaces)}")
    return bullets


def _read_interfaces(usb_root: Path, device_name: str) -> list[UsbInterface]:
    interfaces: list[UsbInterface] = []
    prefix = f"{device_name}:"
    for path in sorted(usb_root.iterdir(), key=lambda item: item.name):
        if not path.name.startswith(prefix):
            continue
        real = _safe_resolve(path)
        raw = _read_fields(real, USB_INTERFACE_FIELDS)
        interfaces.append(
            UsbInterface(
                name=path.name,
                sysfs_path=str(real),
                interface_class=raw.get("bInterfaceClass"),
                interface_subclass=raw.get("bInterfaceSubClass"),
                interface_protocol=raw.get("bInterfaceProtocol"),
                interface_number=raw.get("bInterfaceNumber"),
                alternate_setting=raw.get("bAlternateSetting"),
                driver=_driver_name(real),
                raw=raw,
            )
        )
    return interfaces


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def _read_fields(path: Path, fields: tuple[str, ...]) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in fields:
        value = _read_text(path / field)
        if value is not None:
            values[field] = value
    return values


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError, UnicodeDecodeError):
        return None


def _driver_name(path: Path) -> str | None:
    driver = path / "driver"
    if not driver.exists():
        return None
    try:
        return driver.resolve().name
    except OSError:
        return None


def _speed_label(speed: str) -> str:
    try:
        mbps = float(speed)
    except ValueError:
        return speed
    if mbps >= 1000:
        return f"{mbps / 1000:g} Gbps"
    return f"{mbps:g} Mbps"
