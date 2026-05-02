from __future__ import annotations

from .models import PortSummary, TypeCPort
from .pd import decode_cable_vdo, decode_id_header


def summarize_port(port: TypeCPort) -> PortSummary:
    connected = port.partner is not None or port.cable is not None
    if not connected:
        return PortSummary(
            status="empty",
            headline="Nothing connected",
            subtitle=f"Plug a cable into {port.name} to see what it exposes.",
            bullets=[],
        )

    bullets: list[str] = []

    if port.power_role:
        bullets.append(f"Power role: {port.power_role}")
    if port.data_role:
        bullets.append(f"Data role: {port.data_role}")
    if port.partner and port.partner.accessory_mode:
        bullets.append(f"Accessory mode: {port.partner.accessory_mode}")
    if port.partner and port.partner.alt_modes:
        bullets.append("Alt modes: " + ", ".join(port.partner.alt_modes))

    if port.source_capabilities:
        best = max(port.source_capabilities, key=lambda option: option.max_power_mw)
        bullets.append(f"Source advertises up to {best.watts_label}")
        bullets.extend(
            f"{option.volts_label} @ {option.amps_label} ({option.watts_label})"
            for option in port.source_capabilities
        )

    if port.cable and port.cable.identity:
        cable_identity = port.cable.identity
        if cable_identity.id_header is not None:
            header = decode_id_header(cable_identity.id_header)
            bullets.append(f"Cable identity: {header.product_label}")
        cable_vdo_raw = (
            cable_identity.product_type_vdo1
            or cable_identity.product_type_vdo2
            or cable_identity.product_type_vdo3
        )
        if cable_vdo_raw is not None:
            cable_vdo = decode_cable_vdo(cable_vdo_raw, active=port.cable.active is True)
            bullets.append(f"Cable speed: {cable_vdo.speed_label}")
            bullets.append(
                f"Cable current: {cable_vdo.current_label} at up to "
                f"{cable_vdo.max_volts}V (~{cable_vdo.max_watts}W)"
            )
        elif port.cable.identity.raw:
            bullets.append("Cable identity is exposed, but no cable VDO was found")

    if port.partner and port.partner.identity and port.partner.identity.id_header is not None:
        header = decode_id_header(port.partner.identity.id_header)
        bullets.append(f"Connected device: {header.product_label}")

    if port.cable and port.cable.active is not None:
        bullets.append("Active cable" if port.cable.active else "Passive cable")

    if port.source_capabilities:
        best = max(port.source_capabilities, key=lambda option: option.max_power_mw)
        headline = f"USB-C power source · {best.watts_label}"
        status = "charging"
        subtitle = "Power Delivery source capabilities are available."
    elif port.partner and port.partner.alt_modes:
        headline = "USB-C alt mode device"
        status = "display"
        subtitle = "The kernel reports alternate mode support."
    elif port.cable and port.cable.identity:
        headline = "USB-C cable with identity"
        status = "cable"
        subtitle = "The kernel exposes cable e-marker data."
    elif port.partner:
        headline = "USB-C device connected"
        status = "device"
        subtitle = "A partner is present, but detailed capabilities are limited."
    else:
        headline = "USB-C cable connected"
        status = "cable"
        subtitle = "A cable is present, but detailed capabilities are limited."

    return PortSummary(status=status, headline=headline, subtitle=subtitle, bullets=bullets)
