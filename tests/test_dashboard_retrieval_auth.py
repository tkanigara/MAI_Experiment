from unittest.mock import Mock

import pytest

from agentic.clients.ads_dashboard_client import AdsDashboardClient, DashboardClientConfig
from agentic.config.dashboard_integration import AdsDashboardApiClient
from agentic.config.dashboard_auth import dashboard_read_headers


@pytest.mark.parametrize("adapter", [AdsDashboardClient, AdsDashboardApiClient])
def test_agent_adapters_send_service_token_without_following_redirects(monkeypatch, adapter):
    monkeypatch.setenv("DASHBOARD_RETRIEVAL_TOKEN", "t" * 48)
    session = Mock()
    session.get.return_value.status_code = 200
    session.get.return_value.json.return_value = []
    client = adapter(config=DashboardClientConfig(), session=session)
    request = client._get if isinstance(client, AdsDashboardClient) else client.get
    assert request("/api/clients") == []
    kwargs = session.get.call_args.kwargs
    assert kwargs["headers"] == {"Authorization": "Bearer " + "t" * 48}
    assert kwargs["allow_redirects"] is False


def test_service_token_never_sent_over_remote_plain_http(monkeypatch):
    monkeypatch.setenv("DASHBOARD_RETRIEVAL_TOKEN", "t" * 48)
    with pytest.raises(ValueError, match="HTTPS"):
        dashboard_read_headers("http://staging.example.com")


def test_absent_service_token_does_not_grant_access(monkeypatch):
    monkeypatch.delenv("DASHBOARD_RETRIEVAL_TOKEN", raising=False)
    assert dashboard_read_headers("http://127.0.0.1:8000") == {}
