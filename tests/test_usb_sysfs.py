from pathlib import Path

from whatcable_linux.usb_sysfs import scan_usb_devices, summarize_usb_device, usb_device_bullets


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_scan_usb_devices_fixture(tmp_path: Path) -> None:
    usb = tmp_path / "usb"
    write(usb / "3-7" / "idVendor", "05e3\n")
    write(usb / "3-7" / "idProduct", "0610\n")
    write(usb / "3-7" / "manufacturer", "GenesysLogic\n")
    write(usb / "3-7" / "product", "USB3 Hub\n")
    write(usb / "3-7" / "speed", "5000\n")
    write(usb / "3-7" / "version", "3.10\n")
    write(usb / "3-7" / "bMaxPower", "0mA\n")
    write(usb / "3-7:1.0" / "bInterfaceClass", "09\n")
    write(usb / "3-7:1.0" / "bInterfaceSubClass", "00\n")
    write(usb / "3-7:1.0" / "bInterfaceProtocol", "03\n")
    write(usb / "3-7:1.0" / "bInterfaceNumber", "00\n")

    devices = scan_usb_devices(usb)

    assert len(devices) == 1
    device = devices[0]
    assert device.name == "3-7"
    assert summarize_usb_device(device) == "USB3 Hub · 5 Gbps, USB 3.10"
    assert "USB ID: 05e3:0610 (Genesys Logic)" in usb_device_bullets(device)
    assert len(device.interfaces) == 1
    assert device.interfaces[0].interface_class == "09"


def test_scan_usb_devices_missing_root(tmp_path: Path) -> None:
    assert scan_usb_devices(tmp_path / "missing") == []
