from __future__ import annotations

from .altmode import CableAltModeCompatibility, cable_altmode_compatibility
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
        for altmode in port.partner.alt_modes:
            compatibility = cable_altmode_compatibility(port, altmode)
            compatibility_label = {
                CableAltModeCompatibility.SUPPORTED: "Yes",
                CableAltModeCompatibility.UNSUPPORTED: "No",
                CableAltModeCompatibility.UNKNOWN: "Unknown",
            }[compatibility]
            bullets.append(
                f"Alt mode: {altmode.label} (advertised by device; "
                f"cable compatibility: {compatibility_label})"
            )

    if port.source_capabilities:
        best = max(port.source_capabilities, key=lambda option: option.max_power_mw)
        bullets.append(f"Source advertises up to {best.watts_label}")
        bullets.extend(
            option.detail_label
            for option in port.source_capabilities
        )

    if port.cable and port.cable.identity:
        cable_identity = port.cable.identity
        if cable_identity.id_header is not None:
            header = decode_id_header(cable_identity.id_header)
            bullets.append(f"Cable identity: {header.product_label}")
        cable_vdo_raw = next(
            (
                value
                for value in (
                    cable_identity.product_type_vdo1,
                    cable_identity.product_type_vdo2,
                    cable_identity.product_type_vdo3,
                )
                if value is not None
            ),
            None,
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
        compatibilities = [
            cable_altmode_compatibility(port, altmode)
            for altmode in port.partner.alt_modes
        ]
        if CableAltModeCompatibility.UNSUPPORTED in compatibilities:
            subtitle = "The device advertises an alternate mode, but the cable is incompatible."
        elif all(value is CableAltModeCompatibility.SUPPORTED for value in compatibilities):
            subtitle = "The device advertises an alternate mode and the cable does not prevent it."
        else:
            subtitle = "The device advertises an alternate mode; cable compatibility is unknown."
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
