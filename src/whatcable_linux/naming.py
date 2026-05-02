from __future__ import annotations

USB_CLASS_NAMES = {
    "00": "Per-interface",
    "01": "Audio",
    "02": "Communications",
    "03": "Human Interface Device",
    "05": "Physical",
    "06": "Still Imaging",
    "07": "Printer",
    "08": "Mass Storage",
    "09": "Hub",
    "0a": "CDC Data",
    "0b": "Smart Card",
    "0d": "Content Security",
    "0e": "Video",
    "0f": "Personal Healthcare",
    "10": "Audio/Video",
    "11": "Billboard",
    "12": "USB-C Bridge",
    "dc": "Diagnostic",
    "e0": "Wireless Controller",
    "ef": "Miscellaneous",
    "fe": "Application Specific",
    "ff": "Vendor Specific",
}

USB_VENDOR_NAMES = {
    "05e3": "Genesys Logic",
    "0bda": "Realtek",
    "1d6b": "Linux Foundation",
    "27c6": "Goodix",
    "8087": "Intel",
}


def usb_class_label(class_code: str | None) -> str | None:
    if not class_code:
        return None
    code = class_code.lower()
    name = USB_CLASS_NAMES.get(code)
    return name or class_code


def usb_vendor_label(vendor_id: str | None) -> str | None:
    if not vendor_id:
        return None
    return USB_VENDOR_NAMES.get(vendor_id.lower())
