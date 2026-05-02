from __future__ import annotations

import os
from pathlib import Path

from .models import Identity, PowerOption, TypeCCable, TypeCPartner, TypeCPlug, TypeCPort
from .pd import decode_fixed_supply_pdo, parse_int

PORT_FIELDS = (
    "data_role",
    "power_role",
    "port_type",
    "supported_accessory_modes",
    "usb_power_delivery_revision",
)

PARTNER_FIELDS = (
    "accessory_mode",
    "supports_usb_power_delivery",
)

CABLE_FIELDS = (
    "active",
)

IDENTITY_FIELDS = (
    "id_header",
    "cert_stat",
    "product",
    "product_type_vdo1",
    "product_type_vdo2",
    "product_type_vdo3",
)


def scan(typec_root: Path | str = "/sys/class/typec", pd_root: Path | str = "/sys/class/usb_power_delivery") -> list[TypeCPort]:
    typec_root = Path(typec_root)
    pd_root = Path(pd_root)

    ports = [_read_port(path) for path in _port_paths(typec_root)]
    capabilities = _read_power_delivery_capabilities(pd_root)

    enriched = []
    for port in ports:
        caps = capabilities.get(port.name, [])
        enriched.append(_replace_port_capabilities(port, caps))
    return enriched


def _replace_port_capabilities(port: TypeCPort, source_capabilities: list[PowerOption]) -> TypeCPort:
    return TypeCPort(
        name=port.name,
        sysfs_path=port.sysfs_path,
        data_role=port.data_role,
        power_role=port.power_role,
        port_type=port.port_type,
        supported_accessory_modes=port.supported_accessory_modes,
        usb_power_delivery_revision=port.usb_power_delivery_revision,
        raw=port.raw,
        partner=port.partner,
        cable=port.cable,
        plug=port.plug,
        source_capabilities=source_capabilities,
    )


def _port_paths(typec_root: Path) -> list[Path]:
    if not typec_root.exists():
        return []
    return sorted(
        path for path in typec_root.iterdir()
        if path.name.startswith("port") and "-partner" not in path.name and "-cable" not in path.name and "-plug" not in path.name
    )


def _read_port(path: Path) -> TypeCPort:
    raw = _read_fields(path, PORT_FIELDS)
    partner = _read_partner(path)
    cable = _read_cable(path)
    plug = _read_plug(path)

    return TypeCPort(
        name=path.name,
        sysfs_path=str(path),
        data_role=raw.get("data_role"),
        power_role=raw.get("power_role"),
        port_type=raw.get("port_type"),
        supported_accessory_modes=raw.get("supported_accessory_modes"),
        usb_power_delivery_revision=raw.get("usb_power_delivery_revision"),
        raw=raw,
        partner=partner,
        cable=cable,
        plug=plug,
    )


def _read_partner(port_path: Path) -> TypeCPartner | None:
    path = _first_existing_child(port_path, f"{port_path.name}-partner")
    if path is None:
        return None

    raw = _read_fields(path, PARTNER_FIELDS)
    alt_modes = _read_alt_modes(path)
    return TypeCPartner(
        name=path.name,
        sysfs_path=str(path),
        accessory_mode=raw.get("accessory_mode"),
        supports_usb_power_delivery=_parse_bool(raw.get("supports_usb_power_delivery")),
        identity=_read_identity(path / "identity"),
        alt_modes=alt_modes,
        raw=raw,
    )


def _read_cable(port_path: Path) -> TypeCCable | None:
    path = _first_existing_child(port_path, f"{port_path.name}-cable")
    if path is None:
        return None

    raw = _read_fields(path, CABLE_FIELDS)
    return TypeCCable(
        name=path.name,
        sysfs_path=str(path),
        active=_parse_bool(raw.get("active")),
        identity=_read_identity(path / "identity"),
        raw=raw,
    )


def _read_plug(port_path: Path) -> TypeCPlug | None:
    path = _first_existing_child(port_path, f"{port_path.name}-plug0")
    if path is None:
        return None

    return TypeCPlug(
        name=path.name,
        sysfs_path=str(path),
        identity=_read_identity(path / "identity"),
        raw={},
    )


def _first_existing_child(port_path: Path, name: str) -> Path | None:
    candidates = [
        port_path / name,
        port_path.parent / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_alt_modes(path: Path) -> list[str]:
    modes: list[str] = []
    for child in sorted(path.iterdir()) if path.exists() else []:
        if "-mode" not in child.name and not child.name.startswith(f"{path.name}."):
            continue
        fields = _read_fields(child, ("description", "mode", "svid", "vdo"))
        description = fields.get("description")
        svid = fields.get("svid")
        mode = fields.get("mode")
        if description:
            modes.append(description)
        elif svid and mode:
            modes.append(f"SVID {svid}, mode {mode}")
        elif svid:
            modes.append(f"SVID {svid}")
        else:
            modes.append(child.name)
    return modes


def _read_identity(path: Path) -> Identity | None:
    if not path.exists():
        return None

    raw = _read_fields(path, IDENTITY_FIELDS)
    if not raw:
        return None

    return Identity(
        id_header=parse_int(raw.get("id_header")),
        cert_stat=parse_int(raw.get("cert_stat")),
        product=parse_int(raw.get("product")),
        product_type_vdo1=parse_int(raw.get("product_type_vdo1")),
        product_type_vdo2=parse_int(raw.get("product_type_vdo2")),
        product_type_vdo3=parse_int(raw.get("product_type_vdo3")),
        raw=raw,
    )


def _read_power_delivery_capabilities(pd_root: Path) -> dict[str, list[PowerOption]]:
    if not pd_root.exists():
        return {}

    capabilities: dict[str, list[PowerOption]] = {}
    for path in pd_root.rglob("*"):
        if not path.is_file() or path.name != "source-capabilities":
            continue
        options = _parse_source_capabilities(_read_text(path))
        if not options:
            continue
        port_name = _guess_port_name(path)
        if port_name:
            capabilities.setdefault(port_name, []).extend(options)
    return capabilities


def _parse_source_capabilities(text: str | None) -> list[PowerOption]:
    if not text:
        return []

    options: list[PowerOption] = []
    for token in text.replace(",", " ").split():
        value = parse_int(token)
        if value is None:
            continue
        option = decode_fixed_supply_pdo(value)
        if option is not None:
            options.append(option)
    return options


def _guess_port_name(path: Path) -> str | None:
    try:
        real = path.resolve()
    except OSError:
        real = path

    names = [part for part in real.parts if part.startswith("port")]
    for name in reversed(names):
        if "-partner" not in name and "-cable" not in name and "-plug" not in name:
            return name.split("-", 1)[0]

    env_name = os.environ.get("WHATCABLE_PD_PORT")
    return env_name or None


def _read_fields(path: Path, fields: tuple[str, ...]) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in fields:
        value = _read_text(path / field)
        if value is not None:
            values[field] = value
    return values


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError, UnicodeDecodeError):
        return None


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    text = value.strip().lower()
    if text in {"1", "yes", "true", "y"}:
        return True
    if text in {"0", "no", "false", "n"}:
        return False
    return None
