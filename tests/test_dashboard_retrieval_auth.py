from test_support import OfflineTestCase
from unittest.mock import Mock
from agentic.clients.ads_dashboard_client import (
    AdsDashboardClient,
    DashboardClientConfig,
)
from agentic.config.dashboard_integration import AdsDashboardApiClient
from agentic.config.dashboard_auth import dashboard_read_headers


class TestDashboardRetrievalAuth(OfflineTestCase):

    def test_agent_adapters_send_service_token_without_following_redirects_1(self):
        adapter = AdsDashboardClient
        self.patch_env("DASHBOARD_RETRIEVAL_TOKEN", "t" * 48)
        session = Mock()
        session.get.return_value.status_code = 200
        session.get.return_value.json.return_value = []
        client = adapter(config=DashboardClientConfig(), session=session)
        request = client._get if isinstance(client, AdsDashboardClient) else client.get
        self.assertEqual(request("/api/clients"), [])
        kwargs = session.get.call_args.kwargs
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer " + "t" * 48})
        self.assertIs(kwargs["allow_redirects"], False)

    def test_agent_adapters_send_service_token_without_following_redirects_2(self):
        adapter = AdsDashboardApiClient
        self.patch_env("DASHBOARD_RETRIEVAL_TOKEN", "t" * 48)
        session = Mock()
        session.get.return_value.status_code = 200
        session.get.return_value.json.return_value = []
        client = adapter(config=DashboardClientConfig(), session=session)
        request = client._get if isinstance(client, AdsDashboardClient) else client.get
        self.assertEqual(request("/api/clients"), [])
        kwargs = session.get.call_args.kwargs
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer " + "t" * 48})
        self.assertIs(kwargs["allow_redirects"], False)

    def test_service_token_never_sent_over_remote_plain_http(self):
        self.patch_env("DASHBOARD_RETRIEVAL_TOKEN", "t" * 48)
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            dashboard_read_headers("http://staging.example.com")

    def test_absent_service_token_does_not_grant_access(self):
        self.remove_env("DASHBOARD_RETRIEVAL_TOKEN", raising=False)
        self.assertEqual(dashboard_read_headers("http://127.0.0.1:8000"), {})
