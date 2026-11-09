from pathlib import Path

import pytest

from whatcable_linux.models import Identity, TypeCPartner, TypeCPort
from whatcable_linux.ucsi import scan_ucsi
from whatcable_linux.usb4_debug import scan_usb4_debug
from whatcable_linux.report import scan_system


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def test_ucsi_states(tmp_path):
    assert scan_ucsi(tmp_path, [])[0].properties["state"] == "absent"
    controller = tmp_path / "USBC000:00"
    controller.mkdir()
    assert scan_ucsi(tmp_path, [])[0].properties["state"] == "unbound"
    (controller / "driver").symlink_to(tmp_path / "driver")
    assert scan_ucsi(tmp_path, [])[0].properties["state"] == "bound-without-ports"
    port = TypeCPort("port0", str(controller / "port0"))
    assert scan_ucsi(tmp_path, [port])[0].properties["state"] == "registered-without-identity"
    (controller / "port0").mkdir()
    alias = tmp_path / "port-alias"
    alias.symlink_to(controller / "port0")
    assert scan_ucsi(tmp_path, [TypeCPort("port0", str(alias))])[0].properties["state"] == "registered-without-identity"
    port = TypeCPort("port0", str(controller / "port0"),
                     partner=TypeCPartner("partner", "unused", identity=Identity(id_header=123)))
    assert scan_ucsi(tmp_path, [port])[0].properties["state"] == "identity-available"
    unrelated = TypeCPort("port1", str(tmp_path / "other" / "port1"))
    assert scan_ucsi(tmp_path, [unrelated])[0].properties["state"] == "bound-without-ports"


def test_diagnostic_permission_denied(tmp_path, monkeypatch):
    def denied(path):
        raise PermissionError(path)
    monkeypatch.setattr(Path, "iterdir", denied)
    assert scan_ucsi(tmp_path, [])[0].properties["state"] == "permission-denied"
    assert scan_usb4_debug(tmp_path)[0].properties["state"] == "permission-denied"


def test_debug_counters_only(tmp_path):
    counters = tmp_path / "0-0" / "1" / "counters"
    write(counters, "0 0 0 0x00000001\n")
    write(counters.parent / "margining" / "run", "do not touch")
    assert scan_usb4_debug(tmp_path)[0].properties["counter_snapshot"] == "0 0 0 0x00000001"
    assert (counters.parent / "margining" / "run").read_text() == "do not touch"
    assert scan_usb4_debug(tmp_path / "missing")[0].properties["state"] == "unavailable"


@pytest.mark.parametrize("linked", [True, False])
def test_link_fields_and_explicit_usb_association(tmp_path, linked):
    router = tmp_path / "tb" / "0-1"
    write(router / "tx_speed", "20.0 Gb/s")
    write(router / "rx_speed", "20.0 Gb/s")
    write(router / "tx_lanes", "2")
    write(tmp_path / "usb" / "1-1" / "speed", "10000")
    if linked:
        (router / "port1").mkdir()
        (tmp_path / "usb" / "1-1" / "usb4_port").symlink_to(router / "port1")
    report = scan_system(
        typec_root=tmp_path / "typec", pd_root=tmp_path / "pd", usb_root=tmp_path / "usb",
        thunderbolt_root=tmp_path / "tb", usb4_root=tmp_path / "usb4",
        debug_usb_devices=tmp_path / "debug", chrome_ec_root=tmp_path / "ec",
        chrome_ec_device=tmp_path / "ec-device", acpi_root=tmp_path / "acpi",
        usb4_debug_root=tmp_path / "never-read",
    )
    device = report.advanced_devices[0]
    assert device.negotiated_link.tx_speed == "20.0 Gb/s"
    assert device.negotiated_link.tx_lanes == "2"
    assert device.negotiated_link.usb_devices == (["1-1"] if linked else [])
    assert report.usb_devices[0].speed == "10000"
    assert not any(d.source == "USB4 debugfs" for d in report.advanced_devices)
