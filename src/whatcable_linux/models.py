from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Identity:
    id_header: int | None = None
    cert_stat: int | None = None
    product: int | None = None
    product_type_vdo1: int | None = None
    product_type_vdo2: int | None = None
    product_type_vdo3: int | None = None
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def vendor_id(self) -> int | None:
        if self.id_header is None:
            return None
        return self.id_header & 0xFFFF

    @property
    def product_id(self) -> int | None:
        if self.product is None:
            return None
        return self.product & 0xFFFF


@dataclass(frozen=True)
class TypeCPort:
    name: str
    sysfs_path: str
    data_role: str | None = None
    power_role: str | None = None
    port_type: str | None = None
    supported_accessory_modes: str | None = None
    usb_power_delivery_revision: str | None = None
    raw: dict[str, str] = field(default_factory=dict)
    partner: TypeCPartner | None = None
    cable: TypeCCable | None = None
    plug: TypeCPlug | None = None
    source_capabilities: list[PowerOption] = field(default_factory=list)


@dataclass(frozen=True)
class TypeCPartner:
    name: str
    sysfs_path: str
    accessory_mode: str | None = None
    supports_usb_power_delivery: bool | None = None
    identity: Identity | None = None
    alt_modes: list[str] = field(default_factory=list)
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TypeCCable:
    name: str
    sysfs_path: str
    active: bool | None = None
    identity: Identity | None = None
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TypeCPlug:
    name: str
    sysfs_path: str
    identity: Identity | None = None
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PowerOption:
    voltage_mv: int
    max_current_ma: int
    max_power_mw: int
    raw: int | None = None

    @property
    def watts(self) -> float:
        return self.max_power_mw / 1000

    @property
    def volts_label(self) -> str:
        return f"{self.voltage_mv / 1000:g}V"

    @property
    def amps_label(self) -> str:
        return f"{self.max_current_ma / 1000:.2f}A"

    @property
    def watts_label(self) -> str:
        return f"{self.watts:g}W"


@dataclass(frozen=True)
class PortSummary:
    status: str
    headline: str
    subtitle: str
    bullets: list[str]


@dataclass(frozen=True)
class UsbDevice:
    name: str
    sysfs_path: str
    busnum: str | None = None
    devnum: str | None = None
    devpath: str | None = None
    speed: str | None = None
    version: str | None = None
    id_vendor: str | None = None
    id_product: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    serial: str | None = None
    device_class: str | None = None
    device_subclass: str | None = None
    device_protocol: str | None = None
    max_power: str | None = None
    configuration: str | None = None
    driver: str | None = None
    tx_lanes: str | None = None
    rx_lanes: str | None = None
    interfaces: list[UsbInterface] = field(default_factory=list)
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class UsbInterface:
    name: str
    sysfs_path: str
    interface_class: str | None = None
    interface_subclass: str | None = None
    interface_protocol: str | None = None
    interface_number: str | None = None
    alternate_setting: str | None = None
    driver: str | None = None
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SystemReport:
    typec_ports: list[TypeCPort] = field(default_factory=list)
    usb_devices: list[UsbDevice] = field(default_factory=list)
    advanced_devices: list[AdvancedDevice] = field(default_factory=list)


@dataclass(frozen=True)
class AdvancedDevice:
    source: str
    name: str
    sysfs_path: str | None = None
    summary: str | None = None
    properties: dict[str, str] = field(default_factory=dict)
    raw: dict[str, str] = field(default_factory=dict)
