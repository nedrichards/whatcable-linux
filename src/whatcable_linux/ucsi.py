"""Read-only UCSI evidence; sysfs alone cannot prove firmware initialisation failure."""
from pathlib import Path

from .advanced_sources import _read_text, _safe_iterdir, _safe_resolve
from .models import AdvancedDevice, TypeCPort


def scan_ucsi(acpi_root: Path | str, ports: list[TypeCPort]) -> list[AdvancedDevice]:
    root = Path(acpi_root)
    try:
        entries = list(root.iterdir())
    except OSError as error:
        state = "permission-denied" if isinstance(error, PermissionError) else "unavailable"
        return [AdvancedDevice("UCSI", "controller", summary="ACPI controller discovery unavailable",
                               properties={"state": state})]
    controllers = [p for p in entries if (_read_text(p / "hid") or p.name.split(":")[0]) == "USBC000"]
    if not controllers:
        return [AdvancedDevice("UCSI", "controller", summary="No standard ACPI UCSI controller exposed",
                               properties={"state": "absent", "scope": "ACPI USBC000 only"})]
    result = []
    for controller in sorted(controllers):
        real = _safe_resolve(controller)
        registered = [p for p in ports if _safe_resolve(Path(p.sysfs_path)).is_relative_to(real)]
        # Some drivers register ports below a platform child, still within the ACPI device.
        bound = (controller / "driver").is_symlink() or any(
            (child / "driver").is_symlink() for child in _safe_iterdir(controller)
        )
        state = "unbound"
        if registered:
            state = "registered-without-identity"
            if all(p.partner and p.partner.identity and p.partner.identity.id_header is not None for p in registered):
                state = "identity-available"
        elif bound:
            state = "bound-without-ports"
        result.append(AdvancedDevice(
            "UCSI", controller.name, sysfs_path=str(real), summary=f"UCSI: {state}",
            properties={"state": state, "registered_ports": ", ".join(p.name for p in registered),
                        "initialisation": "No registered ports; failure cannot be confirmed from sysfs" if bound and not registered
                        else "Port registration observed" if registered else "No driver binding observed",
                        "identity_note": "Identity may be absent when disconnected or hidden by firmware"},
        ))
    return result
