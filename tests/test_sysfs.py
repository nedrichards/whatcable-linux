from pathlib import Path

import pytest

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


def test_scan_current_power_delivery_sysfs_abi(tmp_path: Path) -> None:
    typec = tmp_path / "typec"
    pd = tmp_path / "usb_power_delivery"
    write(typec / "port0" / "power_role", "source\n")
    write(typec / "port0" / "port0-partner" / "supports_usb_power_delivery", "yes\n")

    pd_device = tmp_path / "devices" / "port0" / "port0-partner" / "pd0"
    pd.mkdir()
    pd_device.mkdir(parents=True)
    (pd / "pd0").symlink_to(pd_device, target_is_directory=True)
    capabilities = pd_device / "source-capabilities"
    write(capabilities / "1:fixed_supply" / "voltage", "5000\n")
    write(capabilities / "1:fixed_supply" / "maximum_current", "3000\n")
    write(capabilities / "2:variable_supply" / "minimum_voltage", "5000\n")
    write(capabilities / "2:variable_supply" / "maximum_voltage", "12000\n")
    write(capabilities / "2:variable_supply" / "maximum_current", "3000\n")
    write(capabilities / "3:battery" / "minimum_voltage", "9000\n")
    write(capabilities / "3:battery" / "maximum_voltage", "20000\n")
    write(capabilities / "3:battery" / "maximum_power", "60000\n")
    write(capabilities / "4:programmable_supply" / "minimum_voltage", "3300\n")
    write(capabilities / "4:programmable_supply" / "maximum_voltage", "11000\n")
    write(capabilities / "4:programmable_supply" / "maximum_current", "5000\n")
    write(
        capabilities / "5:spr_adjustable_voltage_supply" / "maximum_current_9V_to_15V",
        "3000\n",
    )
    write(
        capabilities / "5:spr_adjustable_voltage_supply" / "maximum_current_15V_to_20V",
        "2000\n",
    )

    port = scan(typec, pd)[0]

    assert [option.supply_type for option in port.source_capabilities] == [
        "fixed_supply",
        "variable_supply",
        "battery",
        "programmable_supply",
        "spr_adjustable_voltage_supply",
        "spr_adjustable_voltage_supply",
    ]
    assert [option.detail_label for option in port.source_capabilities] == [
        "5V @ 3.00A (15W)",
        "5–12V @ 3.00A (36W)",
        "9–20V (60W)",
        "3.3–11V @ 5.00A (55W)",
        "9–15V @ 3.00A (45W)",
        "15–20V @ 2.00A (40W)",
    ]
    assert summarize_port(port).headline == "USB-C power source · 60W"


def test_scan_ignores_typec_directory_removed_during_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    typec = tmp_path / "typec"
    typec.mkdir()
    original_iterdir = Path.iterdir

    def disappearing_iterdir(path: Path):
        if path == typec:
            raise FileNotFoundError(path)
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", disappearing_iterdir)

    assert scan(typec, tmp_path / "missing-pd") == []
