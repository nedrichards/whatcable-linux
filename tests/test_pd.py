from whatcable_linux.pd import decode_cable_vdo, decode_fixed_supply_pdo, decode_id_header


def test_decode_id_header() -> None:
    header = decode_id_header(0x18001234)

    assert header.vendor_id == 0x1234
    assert header.ufp_product_type == 3
    assert header.product_label == "Passive cable"


def test_decode_cable_vdo() -> None:
    vdo = 0x00000242
    cable = decode_cable_vdo(vdo, active=False)

    assert cable.speed_label == "USB 3.2 Gen 2 (10 Gbps)"
    assert cable.current_label == "5 A"
    assert cable.max_volts == 30
    assert cable.max_watts == 150


def test_decode_fixed_supply_pdo() -> None:
    option = decode_fixed_supply_pdo(0x000641F4)

    assert option is not None
    assert option.voltage_mv == 20_000
    assert option.max_current_ma == 5_000
    assert option.max_power_mw == 100_000
