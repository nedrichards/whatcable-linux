from __future__ import annotations

from enum import Enum

from .models import TypeCAltMode, TypeCPort
from .pd import decode_cable_vdo, decode_id_header


DISPLAYPORT_SVID = 0xFF01
DP_CAP_RECEPTACLE = 1 << 6


class CableAltModeCompatibility(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


def cable_altmode_compatibility(
    port: TypeCPort,
    altmode: TypeCAltMode,
) -> CableAltModeCompatibility:
    """Mirror Linux's tri-state Type-C cable alternate-mode check."""
    # DisplayPort only checks a detachable cable. A DP device without the
    # receptacle bit has a captive cable designed as part of that device.
    if altmode.svid == DISPLAYPORT_SVID:
        if altmode.vdo is None:
            return CableAltModeCompatibility.UNKNOWN
        if not altmode.vdo & DP_CAP_RECEPTACLE:
            return CableAltModeCompatibility.SUPPORTED

    if _plug_supports_altmode(port, altmode):
        return CableAltModeCompatibility.SUPPORTED

    cable = port.cable
    if cable is None or cable.identity is None:
        return CableAltModeCompatibility.UNKNOWN

    id_header = cable.identity.id_header
    if id_header is None:
        return CableAltModeCompatibility.UNKNOWN
    if id_header == 0:
        return CableAltModeCompatibility.UNSUPPORTED

    product_type = decode_id_header(id_header).ufp_product_type
    if product_type == 3:  # Passive cable
        cable_vdo = cable.identity.product_type_vdo1
        if cable_vdo is None:
            return CableAltModeCompatibility.UNKNOWN
        speed = decode_cable_vdo(cable_vdo, active=False).speed_bits
        return (
            CableAltModeCompatibility.UNSUPPORTED
            if speed == 0
            else CableAltModeCompatibility.SUPPORTED
        )
    if product_type == 4:  # Active cable
        # If plug modes exist but the partner SVID is unavailable, we cannot
        # tell whether one is the corresponding SOP' mode.
        if altmode.svid is None and port.plug and port.plug.alt_modes:
            return CableAltModeCompatibility.UNKNOWN
        return CableAltModeCompatibility.UNSUPPORTED
    return CableAltModeCompatibility.UNKNOWN


def cable_altmode_explanation(
    port: TypeCPort,
    altmode: TypeCAltMode,
    compatibility: CableAltModeCompatibility | None = None,
) -> str:
    compatibility = compatibility or cable_altmode_compatibility(port, altmode)
    if compatibility is CableAltModeCompatibility.UNKNOWN:
        return "The system has not exposed enough cable identity information to determine compatibility."

    if altmode.svid == DISPLAYPORT_SVID and altmode.vdo is not None and not altmode.vdo & DP_CAP_RECEPTACLE:
        return "This device has a captive cable, so a separate cable compatibility check does not apply."

    if _plug_supports_altmode(port, altmode):
        return "The active cable exposes the corresponding SOP' alternate mode."

    cable = port.cable
    identity = cable.identity if cable else None
    if identity and identity.id_header == 0:
        return "This cable has no e-marker identity and is only guaranteed to carry USB 2.0 data."
    if identity and identity.id_header is not None:
        product_type = decode_id_header(identity.id_header).ufp_product_type
        if product_type == 3 and identity.product_type_vdo1 is not None:
            speed = decode_cable_vdo(identity.product_type_vdo1, active=False).speed_bits
            if speed == 0:
                return "This is a USB 2.0-only passive cable."
            return "This passive cable is faster than USB 2.0 and is not known to prevent this alternate mode."
        if product_type == 4:
            return "This active cable does not expose the corresponding SOP' alternate mode."
    return "The cable is not known to prevent this alternate mode."


def _plug_supports_altmode(port: TypeCPort, altmode: TypeCAltMode) -> bool:
    if port.plug is None or altmode.svid is None:
        return False
    return any(mode.svid == altmode.svid for mode in port.plug.alt_modes)
