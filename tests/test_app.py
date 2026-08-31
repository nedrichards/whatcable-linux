import pytest

from whatcable_linux.altmode import CableAltModeCompatibility
from whatcable_linux.app import BASE_APP_ID, _altmode_verdict_presentation, _application_id


def test_application_id_uses_development_flatpak_identity() -> None:
    assert _application_id(f"{BASE_APP_ID}.Devel") == f"{BASE_APP_ID}.Devel"


def test_application_id_ignores_unexpected_environment_value() -> None:
    assert _application_id("com.example.Unrelated") == BASE_APP_ID
    assert _application_id(None) == BASE_APP_ID


@pytest.mark.parametrize(
    ("compatibility", "label"),
    [
        (CableAltModeCompatibility.SUPPORTED, "Not blocked"),
        (CableAltModeCompatibility.UNSUPPORTED, "Blocked"),
        (CableAltModeCompatibility.UNKNOWN, "Unknown"),
    ],
)
def test_altmode_verdict_describes_cable_restriction_without_overclaiming(
    compatibility: CableAltModeCompatibility,
    label: str,
) -> None:
    verdict, _css_class, _icon_name = _altmode_verdict_presentation(compatibility)

    assert verdict == label
