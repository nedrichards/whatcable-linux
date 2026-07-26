from whatcable_linux.app import BASE_APP_ID, _application_id


def test_application_id_uses_development_flatpak_identity() -> None:
    assert _application_id(f"{BASE_APP_ID}.Devel") == f"{BASE_APP_ID}.Devel"


def test_application_id_ignores_unexpected_environment_value() -> None:
    assert _application_id("com.example.Unrelated") == BASE_APP_ID
    assert _application_id(None) == BASE_APP_ID
