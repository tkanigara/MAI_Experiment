from datetime import date

import pytest

from dashboard.services.meta_ads_api import (
    MetaAdsApiClient,
    MetaAdsApiError,
    MetaAdsSyncService,
    _facebook_page_likes,
    _instagram_profile_visits,
)


class Response:
    def __init__(self, payload, status=200, headers=None):
        self.payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_ad_accounts_paginates_and_uses_bearer_header():
    session = Session([
        Response({"data": [{"id": "act_1", "name": "One", "account_status": 1}], "paging": {"next": "https://graph.facebook.com/next"}}),
        Response({"data": [{"id": "act_2", "name": "Two", "account_status": 2}]})
    ])
    client = MetaAdsApiClient("secret-token", session=session, max_retries=0)
    rows = client.ad_accounts()
    assert [row["id"] for row in rows] == ["act_1", "act_2"]
    assert rows[0]["is_active"] is True
    assert rows[1]["is_active"] is False
    assert all(call[1]["headers"] == {"Authorization": "Bearer secret-token"} for call in session.calls)
    assert all("secret-token" not in call[0] for call in session.calls)


def test_meta_error_does_not_expose_token():
    session = Session([Response({"error": {"code": 190, "message": "Invalid token secret-token"}}, status=401)])
    client = MetaAdsApiClient("secret-token", session=session, max_retries=0)
    with pytest.raises(MetaAdsApiError) as error:
        client.ad_accounts()
    assert "secret-token" not in str(error.value)


def test_rate_limit_is_retried(monkeypatch):
    monkeypatch.setattr("dashboard.services.meta_ads_api.time.sleep", lambda _value: None)
    session = Session([Response({"error": {"code": 4}}, status=429), Response({"data": []})])
    client = MetaAdsApiClient("token", session=session, max_retries=1)
    assert client.ad_accounts() == []
    assert len(session.calls) == 2


def test_profile_growth_metrics_use_platform_specific_meta_values():
    assert _instagram_profile_visits({"instagram_profile_visits": "315"}, {}) == 315
    assert _instagram_profile_visits({}, {"profile_visit_view": 12}) == 12
    assert _facebook_page_likes({"page_like": 7}) == 7
    assert _facebook_page_likes({"profile_visit_view": 53}) == 53
    assert _instagram_profile_visits({}, {}) is None
    assert _facebook_page_likes({}) is None


def test_audience_breakdowns_use_meta_supported_combinations(monkeypatch):
    client = MetaAdsApiClient("token", max_retries=0)
    requested = []
    monkeypatch.setattr(client, "_entities", lambda _account: ({}, {}, {}, []))

    def insights(_account, _start, _end, *, level="ad", breakdowns=None):
        requested.append(breakdowns)
        return []

    monkeypatch.setattr(client, "_insights", insights)
    result = client.fetch_account_snapshot(
        {"id": "act_1"}, date(2026, 7, 1), date(2026, 7, 31),
        ["instagram", "facebook"],
    )
    assert ["age", "gender"] in requested
    assert ["region"] in requested
    assert ["publisher_platform", "age", "gender"] not in requested
    assert ["publisher_platform", "region"] not in requested
    assert "shared All Meta" in result["warnings"][0]


class FakeRepository:
    def __init__(self, accounts):
        self.accounts = accounts
        self.failed = []
        self.completed = []

    def sync_context(self, _client, _period, _accounts, _goals):
        return {"accounts": self.accounts, "period_start": date(2026, 7, 1), "period_end": date(2026, 7, 31), "goals": {"instagram": [{"key": "reach"}]}}

    def resolve_sync_range(self, period_start, date_range):
        return {"preset": "month_to_date", "start": period_start, "end": date(2026, 7, 31)}

    def start_api_snapshot(self, *_args):
        return "11111111-1111-1111-1111-111111111111"

    def fail_api_snapshot(self, import_id, message):
        self.failed.append((import_id, message))

    def complete_api_snapshot(self, *args):
        self.completed.append(args)
        return {"status": "success"}


class FailingApi:
    def fetch_account_snapshot(self, *_args):
        raise MetaAdsApiError("permission denied")


def test_different_currencies_are_rejected_before_snapshot():
    repository = FakeRepository([{"id": "act_1", "currency": "IDR"}, {"id": "act_2", "currency": "USD"}])
    with pytest.raises(ValueError, match="different currencies"):
        MetaAdsSyncService(repository, FailingApi()).sync("client", "period", {"ad_account_ids": ["act_1", "act_2"], "platforms": ["instagram"]})
    assert repository.failed == []


def test_failed_sync_records_failure_without_completing_snapshot():
    repository = FakeRepository([{"id": "act_1", "currency": "IDR", "timezone_name": "Asia/Jakarta"}])
    with pytest.raises(MetaAdsApiError):
        MetaAdsSyncService(repository, FailingApi()).sync("client", "period", {"ad_account_ids": ["act_1"], "platforms": ["instagram"]})
    assert len(repository.failed) == 1
    assert repository.completed == []


def test_api_migration_contains_snapshot_and_account_mapping():
    sql = open("db/migrations/009_meta_ads_api.sql", encoding="utf-8").read()
    assert "client_meta_ad_accounts" in sql
    assert "meta_ads_active_snapshots" in sql
    assert "meta_ads_creatives" in sql
    assert "DROP CONSTRAINT" in sql
