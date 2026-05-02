from pathlib import Path

from whatcable_linux.summary import summarize_port
from whatcable_linux.sysfs import scan


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_scan_typec_fixture(tmp_path: Path) -> None:
    typec = tmp_path / "typec"
    pd = tmp_path / "usb_power_delivery"

    write(typec / "port0" / "power_role", "source\n")
    write(typec / "port0" / "data_role", "host\n")
    write(typec / "port0" / "port_type", "dual\n")
    write(typec / "port0" / "port0-partner" / "supports_usb_power_delivery", "yes\n")
    write(typec / "port0" / "port0-partner" / "identity" / "id_header", "0x40001234\n")
    write(typec / "port0" / "port0-partner" / "identity" / "product", "0x00005678\n")
    write(typec / "port0" / "port0-partner" / "port0-partner.0" / "description", "DisplayPort\n")
    write(typec / "port0" / "port0-cable" / "active", "0\n")
    write(typec / "port0" / "port0-cable" / "identity" / "id_header", "0x18004321\n")
    write(typec / "port0" / "port0-cable" / "identity" / "product_type_vdo1", "0x00000242\n")
    write(pd / "port0-source" / "source-capabilities", "0x0001912c 0x000641f4\n")

    ports = scan(typec, pd)

    assert len(ports) == 1
    port = ports[0]
    assert port.name == "port0"
    assert port.partner is not None
    assert port.cable is not None
    assert len(port.source_capabilities) == 2

    summary = summarize_port(port)
    assert summary.headline == "USB-C power source · 100W"
    assert "Cable speed: USB 3.2 Gen 2 (10 Gbps)" in summary.bullets
    assert "Alt modes: DisplayPort" in summary.bullets


def test_scan_missing_roots(tmp_path: Path) -> None:
    assert scan(tmp_path / "missing-typec", tmp_path / "missing-pd") == []
