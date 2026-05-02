from __future__ import annotations

from pathlib import Path

from .models import AdvancedDevice

ADVANCED_FIELDS = (
    "authorized",
    "device",
    "device_name",
    "device_type",
    "generation",
    "iommu_dma_protection",
    "key",
    "link",
    "maxhopid",
    "nvm_authenticate",
    "nvm_version",
    "rx_speed",
    "rx_lanes",
    "security",
    "tx_speed",
    "tx_lanes",
    "unique_id",
    "vendor",
    "vendor_name",
)


def scan_advanced_sources(
    thunderbolt_root: Path | str = "/sys/bus/thunderbolt/devices",
    usb4_root: Path | str = "/sys/bus/usb4/devices",
    debug_usb_devices: Path | str = "/sys/kernel/debug/usb/devices",
) -> list[AdvancedDevice]:
    devices: list[AdvancedDevice] = []
    devices.extend(_scan_bus("Thunderbolt", Path(thunderbolt_root)))
    devices.extend(_scan_bus("USB4", Path(usb4_root)))
    devices.extend(_scan_debug_usb(Path(debug_usb_devices)))
    return devices


def _scan_bus(source: str, root: Path) -> list[AdvancedDevice]:
    if not root.exists():
        return []

    devices: list[AdvancedDevice] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        real = _safe_resolve(path)
        if not real.is_dir():
            continue
        raw = _read_fields(real, ADVANCED_FIELDS)
        if not raw:
            continue

        label = raw.get("device_name") or raw.get("vendor_name") or path.name
        summary_bits = []
        if "generation" in raw:
            summary_bits.append(f"Gen {raw['generation']}")
        if "security" in raw:
            summary_bits.append(f"Security {raw['security']}")
        if "authorized" in raw:
            summary_bits.append("authorized" if raw["authorized"] == "1" else "not authorized")
        if "tx_speed" in raw or "rx_speed" in raw:
            summary_bits.append(f"TX {raw.get('tx_speed', '?')} / RX {raw.get('rx_speed', '?')}")

        devices.append(
            AdvancedDevice(
                source=source,
                name=path.name,
                sysfs_path=str(real),
                summary=label if not summary_bits else f"{label} · {', '.join(summary_bits)}",
                properties={key: value for key, value in raw.items() if key != "uevent"},
                raw=raw,
            )
        )
    return devices


def _scan_debug_usb(path: Path) -> list[AdvancedDevice]:
    text = _read_text(path)
    if not text:
        return []

    devices: list[AdvancedDevice] = []
    current: dict[str, str] = {}
    index = 0
    for line in text.splitlines():
        if line.startswith("T:"):
            if current:
                devices.append(_debug_entry(index, current, path))
                index += 1
                current = {}
            current["topology"] = line[2:].strip()
        elif line.startswith("D:"):
            current["device"] = line[2:].strip()
        elif line.startswith("P:"):
            current["product_ids"] = line[2:].strip()
        elif line.startswith("S:"):
            key, _, value = line[2:].strip().partition("=")
            if key and value:
                current[key.lower()] = value
        elif line.startswith("C:"):
            current["configuration"] = line[2:].strip()
    if current:
        devices.append(_debug_entry(index, current, path))
    return devices


def _debug_entry(index: int, raw: dict[str, str], path: Path) -> AdvancedDevice:
    name = raw.get("product") or raw.get("manufacturer") or f"debug-usb-{index}"
    bits = [raw[key] for key in ("manufacturer", "serialnumber") if key in raw]
    return AdvancedDevice(
        source="USB debugfs",
        name=f"debug-usb-{index}",
        sysfs_path=str(path),
        summary=name if not bits else f"{name} · {', '.join(bits)}",
        properties=raw,
        raw=raw,
    )


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


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path
