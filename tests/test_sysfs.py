from pathlib import Path

import pytest

from whatcable_linux.altmode import CableAltModeCompatibility, cable_altmode_compatibility
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
    write(typec / "port0" / "port0-partner" / "port0-partner.0" / "svid", "ff01\n")
    write(typec / "port0" / "port0-partner" / "port0-partner.0" / "mode", "1\n")
    write(typec / "port0" / "port0-partner" / "port0-partner.0" / "vdo", "0x00000040\n")
    write(typec / "port0" / "port0-cable" / "type", "passive\n")
    write(typec / "port0" / "port0-cable" / "identity" / "id_header", "0x18004321\n")
    write(typec / "port0" / "port0-cable" / "identity" / "product_type_vdo1", "0x00000242\n")
    write(pd / "port0-source" / "source-capabilities", "0x0001912c 0x000641f4\n")

    ports = scan(typec, pd)

    assert len(ports) == 1
    port = ports[0]
    assert port.name == "port0"
    assert port.partner is not None
    assert port.cable is not None
    assert port.cable.cable_type == "passive"
    assert port.cable.active is False
    assert port.partner.alt_modes[0].svid == 0xFF01
    assert port.partner.alt_modes[0].mode == 1
    assert len(port.source_capabilities) == 2

    summary = summarize_port(port)
    assert summary.headline == "USB-C power source · 100W"
    assert "Cable speed: USB 3.2 Gen 2 (10 Gbps)" in summary.bullets
    assert "Alt mode: DisplayPort (advertised by device; cable compatibility: Yes)" in summary.bullets


def _write_altmode(
    root: Path,
    parent: str,
    *,
    description: str = "DisplayPort",
    svid: str = "ff01",
    mode: int = 1,
    vdo: int = 0x40,
) -> None:
    path = root / "port0" / parent / f"{parent}.0"
    write(path / "description", f"{description}\n")
    write(path / "svid", f"{svid}\n")
    write(path / "mode", f"{mode}\n")
    write(path / "vdo", f"0x{vdo:08x}\n")


def _scan_altmode_fixture(
    tmp_path: Path,
    *,
    id_header: int | None,
    cable_vdo: int | None = None,
    partner_vdo: int = 0x40,
    plug_altmode: bool = False,
):
    typec = tmp_path / "typec"
    _write_altmode(typec, "port0-partner", vdo=partner_vdo)
    write(typec / "port0" / "port0-cable" / "type", "passive\n")
    if id_header is not None:
        write(
            typec / "port0" / "port0-cable" / "identity" / "id_header",
            f"0x{id_header:08x}\n",
        )
    if cable_vdo is not None:
        write(
            typec / "port0" / "port0-cable" / "identity" / "product_type_vdo1",
            f"0x{cable_vdo:08x}\n",
        )
    if plug_altmode:
        _write_altmode(typec, "port0-plug0")
    return scan(typec, tmp_path / "missing-pd")[0]


@pytest.mark.parametrize(
    ("id_header", "cable_vdo", "expected"),
    [
        (None, None, CableAltModeCompatibility.UNKNOWN),
        (0, None, CableAltModeCompatibility.UNSUPPORTED),
        (0x18000001, 0, CableAltModeCompatibility.UNSUPPORTED),
        (0x18000001, 2, CableAltModeCompatibility.SUPPORTED),
        (0x20000001, 2, CableAltModeCompatibility.UNSUPPORTED),
    ],
)
def test_cable_altmode_compatibility_states(
    tmp_path: Path,
    id_header: int | None,
    cable_vdo: int | None,
    expected: CableAltModeCompatibility,
) -> None:
    port = _scan_altmode_fixture(
        tmp_path,
        id_header=id_header,
        cable_vdo=cable_vdo,
    )

    assert port.partner is not None
    assert cable_altmode_compatibility(port, port.partner.alt_modes[0]) is expected


def test_active_cable_matching_sop_prime_altmode_is_supported(tmp_path: Path) -> None:
    port = _scan_altmode_fixture(
        tmp_path,
        id_header=0x20000001,
        cable_vdo=0,
        plug_altmode=True,
    )

    assert port.partner is not None
    assert port.plug is not None
    assert port.plug.alt_modes[0].svid == 0xFF01
    assert cable_altmode_compatibility(
        port, port.partner.alt_modes[0]
    ) is CableAltModeCompatibility.SUPPORTED


def test_displayport_captive_cable_skips_compatibility_check(tmp_path: Path) -> None:
    port = _scan_altmode_fixture(
        tmp_path,
        id_header=0,
        partner_vdo=0,
    )

    assert port.partner is not None
    assert cable_altmode_compatibility(
        port, port.partner.alt_modes[0]
    ) is CableAltModeCompatibility.SUPPORTED


def test_summary_distinguishes_advertised_mode_from_incompatible_cable(tmp_path: Path) -> None:
    port = _scan_altmode_fixture(
        tmp_path,
        id_header=0x18000001,
        cable_vdo=0,
    )

    summary = summarize_port(port)

    assert "Alt mode: DisplayPort (advertised by device; cable compatibility: No)" in summary.bullets
    assert "Cable speed: USB 2.0 (480 Mbps)" in summary.bullets
    assert summary.subtitle == "The device advertises an alternate mode, but the cable is incompatible."


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
