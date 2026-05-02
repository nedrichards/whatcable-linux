from pathlib import Path

from whatcable_linux.advanced_sources import scan_advanced_sources


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_scan_thunderbolt_fixture(tmp_path: Path) -> None:
    thunderbolt = tmp_path / "thunderbolt"
    write(thunderbolt / "0-0" / "authorized", "1\n")
    write(thunderbolt / "0-0" / "generation", "4\n")
    write(thunderbolt / "0-0" / "vendor_name", "Intel\n")
    write(thunderbolt / "domain0" / "security", "user\n")
    write(thunderbolt / "domain0" / "iommu_dma_protection", "1\n")

    devices = scan_advanced_sources(thunderbolt, tmp_path / "missing-usb4", tmp_path / "missing-debug")

    assert len(devices) == 2
    assert devices[0].source == "Thunderbolt"
    assert devices[0].summary == "Intel · Gen 4, authorized"
    assert devices[1].properties["security"] == "user"


def test_scan_debug_usb_fixture(tmp_path: Path) -> None:
    debug = tmp_path / "debug-usb-devices"
    debug.write_text(
        "\n".join(
            [
                "T:  Bus=03 Lev=01 Prnt=01 Port=09 Cnt=01 Dev#=  4 Spd=12  MxCh= 0",
                "D:  Ver= 2.01 Cls=e0(wlcon) Sub=01 Prot=01 MxPS=64 #Cfgs=  1",
                "P:  Vendor=8087 ProdID=0032 Rev= 0.00",
                "S:  Product=Bluetooth Device",
                "S:  Manufacturer=Intel",
            ]
        ),
        encoding="utf-8",
    )

    devices = scan_advanced_sources(tmp_path / "missing-tb", tmp_path / "missing-usb4", debug)

    assert len(devices) == 1
    assert devices[0].source == "USB debugfs"
    assert devices[0].summary == "Bluetooth Device · Intel"
