from __future__ import annotations

import fcntl
import struct
from pathlib import Path
from typing import BinaryIO, Callable

from .models import AdvancedDevice

CROS_EC_COMMAND_HEADER = struct.Struct("=IIIII")
USB_PD_POWER_INFO_RESPONSE = struct.Struct("<BBBBHHHHI")
EC_CMD_USB_PD_POWER_INFO = 0x0103
EC_RESPONSE_SUCCESS = 0
EC_RESPONSE_INVALID_COMMAND = 1
EC_RESPONSE_INVALID_PARAM = 3
EC_MAX_PORTS = 4

ROLE_LABELS = {
    0: "Disconnected",
    1: "Source",
    2: "Sink",
    3: "Sink, not charging",
}

CHARGING_TYPE_LABELS = {
    0: "None",
    1: "USB PD",
    2: "USB Type-C",
    3: "Proprietary",
    4: "BC 1.2 DCP",
    5: "BC 1.2 CDP",
    6: "BC 1.2 SDP",
    7: "Other",
    8: "VBUS",
    9: "Unknown",
}

FRAMEWORK_PORT_LOCATIONS = {
    0: "Right back",
    1: "Right front",
    2: "Left front",
    3: "Left back",
}


class ChromeEcError(Exception):
    pass


class ChromeEcResponseError(ChromeEcError):
    def __init__(self, result: int) -> None:
        self.result = result
        super().__init__(f"EC response code {result}")


def scan_chrome_ec(
    sysfs_root: Path | str = "/sys/class/chromeos/cros_ec",
    device_path: Path | str = "/dev/cros_ec",
    dmi_root: Path | str = "/sys/class/dmi/id",
    *,
    ioctl_fn: Callable[..., int] = fcntl.ioctl,
) -> list[AdvancedDevice]:
    sysfs_root = Path(sysfs_root)
    device_path = Path(device_path)
    is_framework = (_read_text(Path(dmi_root) / "sys_vendor") or "").startswith("Framework")
    version_text = _read_text(sysfs_root / "version")
    version_properties = _parse_version(version_text)
    access_status: str | None = None
    ports: list[AdvancedDevice] = []

    try:
        with device_path.open("rb", buffering=0) as device:
            ports = _read_ports(device, device_path, ioctl_fn, is_framework)
            access_status = "Available"
    except FileNotFoundError:
        access_status = "Device not exposed"
    except PermissionError:
        access_status = "Permission denied"
    except OSError as error:
        access_status = f"Unavailable: {error.strerror or error}"

    devices: list[AdvancedDevice] = []
    if version_properties or sysfs_root.exists() or device_path.exists():
        properties = dict(version_properties)
        if access_status:
            properties["pd_power_info"] = access_status
        devices.append(
            AdvancedDevice(
                source="Chrome EC",
                name="controller",
                sysfs_path=str(sysfs_root),
                summary=_controller_summary(version_properties, access_status),
                properties=properties,
                raw={"version": version_text} if version_text else {},
            )
        )
    devices.extend(ports)
    return devices


def _read_ports(
    device: BinaryIO,
    device_path: Path,
    ioctl_fn: Callable[..., int],
    is_framework: bool,
) -> list[AdvancedDevice]:
    ports: list[AdvancedDevice] = []
    for port in range(EC_MAX_PORTS):
        try:
            values = _read_pd_power_info(device, port, ioctl_fn)
        except ChromeEcResponseError as error:
            if error.result in {EC_RESPONSE_INVALID_COMMAND, EC_RESPONSE_INVALID_PARAM}:
                break
            continue
        except (ChromeEcError, OSError):
            break
        ports.append(_port_device(port, device_path, values, is_framework))
    return ports


def _read_pd_power_info(
    device: BinaryIO,
    port: int,
    ioctl_fn: Callable[..., int],
) -> tuple[int, int, int, int, int, int, int, int, int]:
    response_size = USB_PD_POWER_INFO_RESPONSE.size
    buffer = bytearray(CROS_EC_COMMAND_HEADER.size + response_size)
    CROS_EC_COMMAND_HEADER.pack_into(
        buffer,
        0,
        0,
        EC_CMD_USB_PD_POWER_INFO,
        1,
        response_size,
        0xFF,
    )
    buffer[CROS_EC_COMMAND_HEADER.size] = port

    returned_size = ioctl_fn(device.fileno(), _cros_ec_command_ioctl(), buffer, True)
    _version, _command, _outsize, _insize, result = CROS_EC_COMMAND_HEADER.unpack_from(buffer)
    if result != EC_RESPONSE_SUCCESS:
        raise ChromeEcResponseError(result)
    if returned_size < response_size:
        raise ChromeEcError(
            f"short EC response: expected {response_size} bytes, received {returned_size}"
        )
    return USB_PD_POWER_INFO_RESPONSE.unpack_from(buffer, CROS_EC_COMMAND_HEADER.size)


def _port_device(
    port: int,
    device_path: Path,
    values: tuple[int, int, int, int, int, int, int, int, int],
    is_framework: bool,
) -> AdvancedDevice:
    (
        role,
        charging_type,
        dual_role,
        _reserved,
        voltage_max_mv,
        voltage_now_mv,
        current_max_ma,
        current_limit_ma,
        max_power_uw,
    ) = values
    role_label = ROLE_LABELS.get(role, f"Unknown ({role})")
    charging_label = CHARGING_TYPE_LABELS.get(charging_type, f"Unknown ({charging_type})")
    location = FRAMEWORK_PORT_LOCATIONS.get(port, f"Port {port}") if is_framework else f"Port {port}"
    max_power_mw = max_power_uw // 1000
    properties = {
        "location": location,
        "role": role_label,
        "charging_type": charging_label,
        "dual_role": "Yes" if dual_role else "No",
        "voltage_now": _volts(voltage_now_mv),
        "voltage_max": _volts(voltage_max_mv),
        "current_limit": _amps(current_limit_ma),
        "current_max": _amps(current_max_ma),
        "max_power": _watts(max_power_mw),
    }
    raw = {
        "role": str(role),
        "charging_type": str(charging_type),
        "dual_role": str(dual_role),
        "voltage_max_mv": str(voltage_max_mv),
        "voltage_now_mv": str(voltage_now_mv),
        "current_max_ma": str(current_max_ma),
        "current_limit_ma": str(current_limit_ma),
        "max_power_uw": str(max_power_uw),
    }
    return AdvancedDevice(
        source="Framework EC" if is_framework else "Chrome EC",
        name=f"port{port}",
        sysfs_path=str(device_path),
        summary=_port_summary(
            location,
            role_label,
            charging_label,
            voltage_now_mv,
            current_limit_ma,
            max_power_mw,
        ),
        properties=properties,
        raw=raw,
    )


def _port_summary(
    location: str,
    role: str,
    charging_type: str,
    voltage_mv: int,
    current_ma: int,
    max_power_mw: int,
) -> str:
    if role == "Disconnected":
        return f"{location} · Disconnected"
    bits = [location, role]
    if charging_type != "None":
        bits.append(charging_type)
    if voltage_mv and current_ma:
        bits.append(f"{_volts(voltage_mv)}, {_amps(current_ma)}")
    elif voltage_mv:
        bits.append(_volts(voltage_mv))
    elif current_ma:
        bits.append(_amps(current_ma))
    if max_power_mw:
        bits.append(f"up to {_watts(max_power_mw)}")
    return " · ".join(bits)


def is_chrome_ec_port(device: AdvancedDevice) -> bool:
    return (
        device.name.startswith("port")
        and device.source in {"Chrome EC", "Framework EC"}
        and "role" in device.properties
    )


def chrome_ec_port_title(device: AdvancedDevice) -> str:
    return device.properties.get("location", device.name)


def chrome_ec_port_subtitle(device: AdvancedDevice) -> str:
    title = chrome_ec_port_title(device)
    summary = device.summary or device.properties.get("role") or device.name
    return summary.removeprefix(f"{title} · ")


def chrome_ec_port_status(device: AdvancedDevice) -> str:
    role = device.properties.get("role")
    if role == "Disconnected":
        return "empty"
    if role == "Source":
        return "source"
    if role == "Sink" and device.properties.get("charging_type") not in {None, "None"}:
        return "charging"
    return "device"


def _parse_version(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator and value.strip():
            values[key.strip().lower().replace(" ", "_")] = value.strip()
    return values


def _controller_summary(properties: dict[str, str], access_status: str | None) -> str:
    version = properties.get("rw_version") or properties.get("ro_version")
    bits = [value for value in (version, access_status) if value]
    return " · ".join(bits) if bits else "Chrome EC detected"


def _volts(millivolts: int) -> str:
    return f"{millivolts / 1000:g} V"


def _amps(milliamps: int) -> str:
    return f"{milliamps / 1000:g} A"


def _watts(milliwatts: int) -> str:
    return f"{milliwatts / 1000:g} W"


def _cros_ec_command_ioctl() -> int:
    # Linux _IOWR(0xEC, 0, struct cros_ec_command), whose fixed header is 20 bytes.
    read_write = 3
    return (
        (read_write << 30)
        | (CROS_EC_COMMAND_HEADER.size << 16)
        | (0xEC << 8)
    )


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError, UnicodeDecodeError):
        return None
