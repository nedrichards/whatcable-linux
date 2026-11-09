"""Optional USB4 debugfs snapshot. Never reads margining controls or writes files."""
from pathlib import Path

from .models import AdvancedDevice


def scan_usb4_debug(root: Path | str = "/sys/kernel/debug/thunderbolt") -> list[AdvancedDevice]:
    root = Path(root)
    result = []
    try:
        routers = sorted(root.iterdir())
        for router in routers:
            for adapter in sorted(router.iterdir()):
                if not adapter.name.isdecimal():
                    continue
                path = adapter / "counters"
                try:
                    value = path.read_text(encoding="utf-8").strip()
                    state = "available"
                except FileNotFoundError:
                    continue
                except (OSError, UnicodeError):
                    value, state = "", "unreadable"
                result.append(AdvancedDevice(
                    "USB4 debugfs", f"{router.name}/{adapter.name}", sysfs_path=str(path),
                    summary=f"Adapter counters: {state}",
                    properties={"state": state, "counter_snapshot": value,
                                "interpretation": "Kernel-format snapshot; not a cable capability or error rate"},
                ))
    except OSError as error:
        state = "permission-denied" if isinstance(error, PermissionError) else "unavailable"
        result.append(AdvancedDevice("USB4 debugfs", "availability", properties={"state": state}))
    if not result:
        result.append(AdvancedDevice("USB4 debugfs", "availability", properties={"state": "counters-not-exposed"}))
    return result
