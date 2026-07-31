from dashboard.repositories.dashboard_repository import (
    available_client_code,
    client_code_base,
)


def test_client_code_base_creates_readable_slug():
    assert client_code_base("  Dunlop Indonesia  ") == "dunlop-indonesia"
    assert client_code_base("Café & Resto") == "cafe-resto"


def test_client_code_base_has_fallback_for_non_ascii_name():
    assert client_code_base("東京") == "client"


def test_available_client_code_uses_first_free_suffix():
    assert available_client_code("mai", []) == "mai"
    assert available_client_code("mai", ["mai"]) == "mai-2"
    assert available_client_code("mai", ["mai", "mai-2", "mai-4"]) == "mai-3"
