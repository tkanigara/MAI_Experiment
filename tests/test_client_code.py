from test_support import OfflineTestCase
from dashboard.repositories.dashboard_repository import (
    available_client_code,
    client_code_base,
)


class TestClientCode(OfflineTestCase):

    def test_client_code_base_creates_readable_slug(self):
        self.assertEqual(client_code_base("  Dunlop Indonesia  "), "dunlop-indonesia")
        self.assertEqual(client_code_base("Café & Resto"), "cafe-resto")

    def test_client_code_base_has_fallback_for_non_ascii_name(self):
        self.assertEqual(client_code_base("東京"), "client")

    def test_available_client_code_uses_first_free_suffix(self):
        self.assertEqual(available_client_code("mai", []), "mai")
        self.assertEqual(available_client_code("mai", ["mai"]), "mai-2")
        self.assertEqual(
            available_client_code("mai", ["mai", "mai-2", "mai-4"]), "mai-3"
        )
