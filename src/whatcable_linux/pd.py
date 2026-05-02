from __future__ import annotations

from dataclasses import dataclass

from .models import PowerOption


PRODUCT_TYPES = {
    0: "Unspecified",
    1: "USB hub",
    2: "USB peripheral",
    3: "Passive cable",
    4: "Active cable",
    5: "Alternate mode adapter",
    6: "VCONN-powered device",
    7: "Other",
}

CABLE_SPEEDS = {
    0: ("USB 2.0", 0.48),
    1: ("USB 3.2 Gen 1", 5),
    2: ("USB 3.2 Gen 2", 10),
    3: ("USB4 Gen 3", 40),
    4: ("USB4 Gen 4", 80),
}

CABLE_CURRENTS = {
    0: ("USB default", 3.0),
    1: ("3 A", 3.0),
    2: ("5 A", 5.0),
}


@dataclass(frozen=True)
class IdHeader:
    usb_comm_host: bool
    usb_comm_device: bool
    modal_operation: bool
    ufp_product_type: int
    dfp_product_type: int
    vendor_id: int

    @property
    def product_label(self) -> str:
        product_type = self.ufp_product_type or self.dfp_product_type
        return PRODUCT_TYPES.get(product_type, "Unknown")


@dataclass(frozen=True)
class CableVdo:
    speed_bits: int
    current_bits: int
    max_voltage_encoded: int
    active: bool
    vbus_through_cable: bool

    @property
    def speed_label(self) -> str:
        label, gbps = CABLE_SPEEDS.get(self.speed_bits, ("Unknown speed", 0))
        if gbps >= 1:
            return f"{label} ({gbps:g} Gbps)"
        if gbps > 0:
            return f"{label} ({gbps * 1000:g} Mbps)"
        return label

    @property
    def current_label(self) -> str:
        label, _amps = CABLE_CURRENTS.get(self.current_bits, ("Unknown", 3.0))
        return label

    @property
    def max_volts(self) -> int:
        return {0: 20, 1: 30, 2: 40, 3: 50}.get(self.max_voltage_encoded, 20)

    @property
    def max_watts(self) -> int:
        _label, amps = CABLE_CURRENTS.get(self.current_bits, ("USB default", 3.0))
        return round(self.max_volts * amps)


def decode_id_header(vdo: int) -> IdHeader:
    return IdHeader(
        usb_comm_host=bool((vdo >> 31) & 1),
        usb_comm_device=bool((vdo >> 30) & 1),
        modal_operation=bool((vdo >> 26) & 1),
        ufp_product_type=(vdo >> 27) & 0b111,
        dfp_product_type=(vdo >> 23) & 0b111,
        vendor_id=vdo & 0xFFFF,
    )


def decode_cable_vdo(vdo: int, *, active: bool) -> CableVdo:
    return CableVdo(
        speed_bits=vdo & 0b111,
        current_bits=(vdo >> 5) & 0b11,
        max_voltage_encoded=(vdo >> 9) & 0b11,
        active=active,
        vbus_through_cable=bool((vdo >> 4) & 1),
    )


def decode_fixed_supply_pdo(pdo: int) -> PowerOption | None:
    supply_type = (pdo >> 30) & 0b11
    if supply_type != 0:
        return None

    current_10ma = pdo & 0x3FF
    voltage_50mv = (pdo >> 10) & 0x3FF
    voltage_mv = voltage_50mv * 50
    current_ma = current_10ma * 10
    if voltage_mv <= 0 or current_ma <= 0:
        return None

    return PowerOption(
        voltage_mv=voltage_mv,
        max_current_ma=current_ma,
        max_power_mw=voltage_mv * current_ma // 1000,
        raw=pdo,
    )


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(text, 0)
    except ValueError:
        return None
