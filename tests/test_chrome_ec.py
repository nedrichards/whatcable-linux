import struct
from pathlib import Path

from whatcable_linux.chrome_ec import (
    CROS_EC_COMMAND_HEADER,
    EC_CMD_USB_PD_POWER_INFO,
    EC_RESPONSE_INVALID_PARAM,
    USB_PD_POWER_INFO_RESPONSE,
    _cros_ec_command_ioctl,
    chrome_ec_port_status,
    chrome_ec_port_subtitle,
    chrome_ec_port_title,
    is_chrome_ec_port,
    scan_chrome_ec,
)


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_scan_chrome_ec_reads_framework_pd_ports(tmp_path: Path) -> None:
    sysfs = tmp_path / "cros_ec"
    device = tmp_path / "cros_ec_device"
    dmi = tmp_path / "dmi"
    write(
        sysfs / "version",
        "RO version: hx20_v0.0.1\nFirmware copy: RO\nBoard version: 12\n",
    )
    write(dmi / "sys_vendor", "Framework\n")
    device.touch()

    responses = {
        0: (2, 1, 0, 0, 20_000, 19_776, 2_250, 2_250, 45_000_000),
        1: (0, 0, 0, 0, 0, 0, 1_500, 0, 0),
    }

    def fake_ioctl(_fd: int, _request: int, buffer: bytearray, _mutate: bool) -> int:
        version, command, outsize, insize, _result = CROS_EC_COMMAND_HEADER.unpack_from(buffer)
        assert version == 0
        assert command == EC_CMD_USB_PD_POWER_INFO
        assert outsize == 1
        assert insize == USB_PD_POWER_INFO_RESPONSE.size
        port = buffer[CROS_EC_COMMAND_HEADER.size]
        result = 0 if port in responses else EC_RESPONSE_INVALID_PARAM
        CROS_EC_COMMAND_HEADER.pack_into(
            buffer, 0, version, command, outsize, insize, result
        )
        if port in responses:
            USB_PD_POWER_INFO_RESPONSE.pack_into(
                buffer, CROS_EC_COMMAND_HEADER.size, *responses[port]
            )
        return USB_PD_POWER_INFO_RESPONSE.size

    devices = scan_chrome_ec(sysfs, device, dmi, ioctl_fn=fake_ioctl)

    assert len(devices) == 3
    assert devices[0].source == "Chrome EC"
    assert devices[0].properties["pd_power_info"] == "Available"
    assert devices[1].source == "Framework EC"
    assert devices[1].summary == "Right back · Sink · USB PD · 19.776 V, 2.25 A · up to 45 W"
    assert devices[1].properties["max_power"] == "45 W"
    assert devices[2].summary == "Right front · Disconnected"
    assert is_chrome_ec_port(devices[1])
    assert chrome_ec_port_title(devices[1]) == "Right back"
    assert chrome_ec_port_subtitle(devices[1]) == "Sink · USB PD · 19.776 V, 2.25 A · up to 45 W"
    assert chrome_ec_port_status(devices[1]) == "charging"
    assert chrome_ec_port_status(devices[2]) == "empty"


def test_scan_chrome_ec_reports_missing_device_without_failing(tmp_path: Path) -> None:
    sysfs = tmp_path / "cros_ec"
    write(sysfs / "version", "RO version: test-version\n")

    devices = scan_chrome_ec(
        sysfs,
        tmp_path / "missing-device",
        tmp_path / "missing-dmi",
    )

    assert len(devices) == 1
    assert devices[0].summary == "test-version · Device not exposed"
    assert devices[0].properties["pd_power_info"] == "Device not exposed"


def test_chrome_ec_ioctl_header_has_linux_uapi_size() -> None:
    assert CROS_EC_COMMAND_HEADER.size == 20
    assert USB_PD_POWER_INFO_RESPONSE.size == 16
    assert struct.calcsize("=IIIII") == 20
    assert _cros_ec_command_ioctl() == 0xC014EC00
