from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from dashboard import main
from dashboard.services.auth import (
    AuthConfig,
    AuthError,
    GoogleOAuthService,
    safe_next_path,
    token_hash,
)


AUTH_ENV = {
    "DASHBOARD_AUTH_MODE": "google",
    "DASHBOARD_PUBLIC_BASE_URL": "http://localhost:8000",
    "DASHBOARD_GOOGLE_OAUTH_CLIENT_ID": "test-client.apps.googleusercontent.com",
    "DASHBOARD_GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
    "DASHBOARD_ALLOWED_EMAIL_DOMAIN": "mai.co.id",
    "DASHBOARD_SESSION_TTL_DAYS": "7",
    "DASHBOARD_OAUTH_CLOCK_SKEW_SECONDS": "60",
}


def test_safe_next_path_rejects_external_destinations():
    assert safe_next_path("/ads/clients?month=august") == "/ads/clients?month=august"
    assert safe_next_path("https://example.com") == "/"
    assert safe_next_path("//example.com/path") == "/"
    assert safe_next_path("/\\example.com") == "/"


def test_auth_config_uses_seven_day_absolute_session():
    with patch.dict("os.environ", AUTH_ENV, clear=False):
        config = AuthConfig.from_env()
    assert config.session_ttl_days == 7
    assert config.oauth_clock_skew_seconds == 60
    assert config.callback_url == "http://localhost:8000/api/auth/google/callback"
    assert config.secure_cookie is False


def test_disabled_auth_is_only_allowed_on_localhost():
    service = GoogleOAuthService(Mock())
    with patch.dict(
        "os.environ",
        {
            "DASHBOARD_AUTH_MODE": "disabled",
            "DASHBOARD_PUBLIC_BASE_URL": "http://localhost:8000",
        },
        clear=False,
    ):
        assert service.local_auth_disabled() is True
        assert service.local_development_user()["name"] == "Local Development"

    with (
        patch.dict(
            "os.environ",
            {
                "DASHBOARD_AUTH_MODE": "disabled",
                "DASHBOARD_PUBLIC_BASE_URL": "https://staging.mai.co.id",
            },
            clear=False,
        ),
        pytest.raises(AuthError) as error,
    ):
        service.validate_runtime()
    assert error.value.code == "AUTH_CONFIG_ERROR"


def test_local_login_creates_database_backed_session():
    service = GoogleOAuthService(Mock())
    service.repository = Mock()
    service.repository.upsert_user.return_value = {
        "id": "local-user-1",
        "email": "local@mai.co.id",
        "display_name": "Local Development",
        "avatar_url": None,
        "is_active": True,
    }
    service.repository.create_session.return_value = {"id": "local-session-1"}
    with patch.dict(
        "os.environ",
        {
            "DASHBOARD_AUTH_MODE": "local",
            "DASHBOARD_PUBLIC_BASE_URL": "http://localhost:8000",
            "DASHBOARD_SESSION_TTL_DAYS": "7",
        },
        clear=False,
    ):
        result = service.create_local_session("/ads/clients", "pytest")

    assert result["next_path"] == "/ads/clients"
    assert result["session_ttl_days"] == 7
    service.repository.upsert_user.assert_called_once()
    service.repository.create_session.assert_called_once()


def configured_service() -> GoogleOAuthService:
    service = GoogleOAuthService(Mock())
    service.repository = Mock()
    service.repository.consume_login_attempt.return_value = {
        "code_verifier": "verifier",
        "next_path": "/ads/clients",
    }
    service.repository.upsert_user.return_value = {
        "id": "user-1",
        "email": "person@mai.co.id",
        "display_name": "MAI Person",
        "avatar_url": None,
        "is_active": True,
    }
    service.repository.create_session.return_value = {
        "id": "session-1",
        "created_at": datetime.now(timezone.utc),
    }
    return service


def google_response():
    response = Mock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = {"id_token": "signed-google-token"}
    return response


def test_complete_login_accepts_verified_workspace_account():
    service = configured_service()
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "google-user-1",
        "email": "person@mai.co.id",
        "email_verified": True,
        "hd": "mai.co.id",
        "name": "MAI Person",
    }
    with (
        patch.dict("os.environ", AUTH_ENV, clear=False),
        patch("dashboard.services.auth.requests.post", return_value=google_response()),
        patch(
            "dashboard.services.auth.google_id_token.verify_oauth2_token",
            return_value=claims,
        ) as verify_token,
    ):
        result = service.complete_login("code", "state", "state", "pytest")

    assert result["next_path"] == "/ads/clients"
    assert 6.99 < (result["expires_at"] - datetime.now(timezone.utc)).total_seconds() / 86400 <= 7
    assert verify_token.call_args.kwargs["clock_skew_in_seconds"] == 60
    service.repository.create_session.assert_called_once()


def test_auth_config_rejects_excessive_oauth_clock_skew():
    env = {**AUTH_ENV, "DASHBOARD_OAUTH_CLOCK_SKEW_SECONDS": "301"}
    with (
        patch.dict("os.environ", env, clear=False),
        pytest.raises(AuthError) as error,
    ):
        AuthConfig.from_env()
    assert error.value.code == "AUTH_CONFIG_ERROR"


@pytest.mark.parametrize(
    "email,hosted_domain,verified,expected_code",
    [
        ("person@gmail.com", "", True, "DOMAIN_NOT_ALLOWED"),
        ("person@mai.co.id", "other.co.id", True, "DOMAIN_NOT_ALLOWED"),
        ("person@mai.co.id", "mai.co.id", False, "EMAIL_NOT_VERIFIED"),
    ],
)
def test_complete_login_rejects_invalid_identity(
    email,
    hosted_domain,
    verified,
    expected_code,
):
    service = configured_service()
    claims = {
        "iss": "accounts.google.com",
        "sub": "google-user-1",
        "email": email,
        "email_verified": verified,
        "hd": hosted_domain,
    }
    with (
        patch.dict("os.environ", AUTH_ENV, clear=False),
        patch("dashboard.services.auth.requests.post", return_value=google_response()),
        patch("dashboard.services.auth.google_id_token.verify_oauth2_token", return_value=claims),
        pytest.raises(AuthError) as error,
    ):
        service.complete_login("code", "state", "state", "pytest")
    assert error.value.code == expected_code
    service.repository.create_session.assert_not_called()


def test_complete_login_reports_google_token_exchange_failure():
    service = configured_service()
    response = Mock()
    response.ok = False
    response.status_code = 401
    response.json.return_value = {"error": "invalid_client"}
    with (
        patch.dict("os.environ", AUTH_ENV, clear=False),
        patch("dashboard.services.auth.requests.post", return_value=response),
        pytest.raises(AuthError) as error,
    ):
        service.complete_login("code", "state", "state", "pytest")
    assert error.value.code == "OAUTH_TOKEN_EXCHANGE_FAILED"


def test_complete_login_reports_invalid_google_id_token():
    service = configured_service()
    with (
        patch.dict("os.environ", AUTH_ENV, clear=False),
        patch("dashboard.services.auth.requests.post", return_value=google_response()),
        patch(
            "dashboard.services.auth.google_id_token.verify_oauth2_token",
            side_effect=ValueError("invalid token"),
        ),
        pytest.raises(AuthError) as error,
    ):
        service.complete_login("code", "state", "state", "pytest")
    assert error.value.code == "OAUTH_ID_TOKEN_INVALID"


def test_csrf_compares_hashed_token():
    service = configured_service()
    session = {"csrf_token_hash": token_hash("csrf-value")}
    assert service.validate_csrf(session, "csrf-value") is True
    assert service.validate_csrf(session, "different") is False


def test_dashboard_api_requires_session_without_test_override():
    test_user = main.app.state.auth_test_user
    del main.app.state.auth_test_user
    try:
        with (
            patch.dict("os.environ", AUTH_ENV, clear=False),
            patch.object(main.auth_service, "current_session", return_value=None),
        ):
            response = TestClient(main.app).get("/api/clients")
        assert response.status_code == 401
        assert response.json()["code"] == "AUTH_REQUIRED"
    finally:
        main.app.state.auth_test_user = test_user


def test_browser_deep_link_redirects_to_login():
    test_user = main.app.state.auth_test_user
    del main.app.state.auth_test_user
    try:
        with (
            patch.dict("os.environ", AUTH_ENV, clear=False),
            patch.object(main.auth_service, "current_session", return_value=None),
        ):
            response = TestClient(main.app).get(
                "/ads/clients/example?month=august",
                follow_redirects=False,
            )
        assert response.status_code == 303
        assert response.headers["location"] == (
            "/login?next=%2Fads%2Fclients%2Fexample%3Fmonth%3Daugust"
        )
    finally:
        main.app.state.auth_test_user = test_user


def test_unsafe_api_request_requires_csrf_token():
    test_user = main.app.state.auth_test_user
    del main.app.state.auth_test_user
    session = {
        "user_id": "user-1",
        "email": "person@mai.co.id",
        "display_name": "MAI Person",
        "avatar_url": None,
        "csrf_token_hash": token_hash("expected-token"),
    }
    try:
        with (
            patch.dict("os.environ", AUTH_ENV, clear=False),
            patch.object(main.auth_service, "current_session", return_value=session),
        ):
            client = TestClient(main.app)
            client.cookies.set("mai_dashboard_session", "session-value")
            response = client.post(
                "/api/clients",
                json={"client_name": "Blocked before handler"},
            )
        assert response.status_code == 403
        assert response.json()["code"] == "CSRF_INVALID"
    finally:
        main.app.state.auth_test_user = test_user


def test_local_disabled_mode_skips_login_without_oauth_credentials():
    test_user = main.app.state.auth_test_user
    del main.app.state.auth_test_user
    try:
        with patch.dict(
            "os.environ",
            {
                "DASHBOARD_AUTH_MODE": "disabled",
                "DASHBOARD_PUBLIC_BASE_URL": "http://localhost:8000",
                "DASHBOARD_GOOGLE_OAUTH_CLIENT_ID": "",
                "DASHBOARD_GOOGLE_OAUTH_CLIENT_SECRET": "",
            },
            clear=False,
        ):
            response = TestClient(main.app, base_url="http://localhost:8000").get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["user"]["local_auth_disabled"] is True
    finally:
        main.app.state.auth_test_user = test_user


def test_healthcheck_is_public():
    test_user = main.app.state.auth_test_user
    del main.app.state.auth_test_user
    try:
        response = TestClient(main.app).get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        main.app.state.auth_test_user = test_user


@pytest.fixture
def protected_client(monkeypatch):
    monkeypatch.delattr(main.app.state, "auth_test_user")
    for key, value in AUTH_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("DASHBOARD_RETRIEVAL_TOKEN", "r" * 48)
    monkeypatch.setattr(main.auth_service, "current_session", lambda token: None)
    return TestClient(main.app, base_url="http://localhost:8000")


def test_retrieval_service_can_read_but_not_write_or_create_session(protected_client):
    headers = {"Authorization": "Bearer " + "r" * 48}
    with patch.object(main.repository, "clients", return_value=[]):
        assert protected_client.get("/api/clients", headers=headers).status_code == 200
    for method, path in [
        ("GET", "/api/auth/me"),
        ("GET", "/api/report-jobs"),
        ("POST", "/api/clients"),
        ("PUT", "/api/ads/clients/example/periods/example/configuration"),
    ]:
        assert protected_client.request(method, path, headers=headers).status_code == 401


@pytest.mark.parametrize("header", ["Bearer wrong", "Basic " + "r" * 48, "Bearer "])
def test_retrieval_invalid_credentials_rejected(protected_client, header):
    response = protected_client.get("/api/clients", headers={"Authorization": header})
    assert response.status_code == 401


@pytest.mark.parametrize("mode", ["local", "disabled"])
def test_local_mode_rejects_non_loopback_request(protected_client, monkeypatch, mode):
    monkeypatch.setenv("DASHBOARD_AUTH_MODE", mode)
    response = protected_client.post(
        "http://192.168.1.12:8000/api/auth/local/login", json={}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "LOCAL_ONLY"


def test_development_session_not_accepted_after_enabling_google():
    service = configured_service()
    service.repository.session.return_value = {
        "email": "local@mai.co.id", "google_subject": "local-development"
    }
    with patch.dict("os.environ", AUTH_ENV, clear=False):
        assert service.current_session("previous-local-session") is None


def test_logout_revokes_session_and_clears_cookies(protected_client, monkeypatch):
    session = {
        "user_id": "user-1", "email": "person@mai.co.id",
        "display_name": "MAI Person", "csrf_token_hash": token_hash("csrf"),
    }
    monkeypatch.setattr(main.auth_service, "current_session", lambda token: session)
    protected_client.cookies.set("mai_dashboard_session", "session-token")
    with patch.object(main.auth_service, "revoke") as revoke:
        response = protected_client.post(
            "/api/auth/logout", headers={"X-CSRF-Token": "csrf"}
        )
    assert response.status_code == 200
    revoke.assert_called_once_with("session-token")
    cookies = response.headers.get_list("set-cookie")
    assert any("mai_dashboard_session=" in cookie and "Max-Age=0" in cookie for cookie in cookies)
    assert any("mai_dashboard_csrf=" in cookie and "Max-Age=0" in cookie for cookie in cookies)
