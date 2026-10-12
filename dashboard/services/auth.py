from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token
from sqlalchemy import text
from sqlalchemy.engine import Engine


SESSION_COOKIE_NAME = "mai_dashboard_session"
CSRF_COOKIE_NAME = "mai_dashboard_csrf"
OAUTH_STATE_COOKIE_NAME = "mai_oauth_state"
OAUTH_ATTEMPT_TTL_SECONDS = 600
AUTH_MODES = {"google", "local", "disabled"}
LOCAL_AUTH_HOSTS = {"localhost", "127.0.0.1", "::1"}
logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    def __init__(self, message: str, code: str = "AUTH_FAILED"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AuthConfig:
    public_base_url: str
    client_id: str
    client_secret: str
    allowed_domain: str
    session_ttl_days: int
    oauth_clock_skew_seconds: int

    @classmethod
    def from_env(cls) -> "AuthConfig":
        raw_ttl = str(os.getenv("DASHBOARD_SESSION_TTL_DAYS") or "7").strip()
        try:
            ttl = int(raw_ttl)
        except ValueError as exc:
            raise AuthError(
                "DASHBOARD_SESSION_TTL_DAYS must be an integer.",
                "AUTH_CONFIG_ERROR",
            ) from exc
        raw_clock_skew = str(
            os.getenv("DASHBOARD_OAUTH_CLOCK_SKEW_SECONDS") or "60"
        ).strip()
        try:
            clock_skew = int(raw_clock_skew)
        except ValueError as exc:
            raise AuthError(
                "DASHBOARD_OAUTH_CLOCK_SKEW_SECONDS must be an integer.",
                "AUTH_CONFIG_ERROR",
            ) from exc
        config = cls(
            public_base_url=str(
                os.getenv("DASHBOARD_PUBLIC_BASE_URL") or ""
            ).strip().rstrip("/"),
            client_id=str(
                os.getenv("DASHBOARD_GOOGLE_OAUTH_CLIENT_ID") or ""
            ).strip(),
            client_secret=str(
                os.getenv("DASHBOARD_GOOGLE_OAUTH_CLIENT_SECRET") or ""
            ).strip(),
            allowed_domain=str(
                os.getenv("DASHBOARD_ALLOWED_EMAIL_DOMAIN") or "mai.co.id"
            ).strip().lower().lstrip("@"),
            session_ttl_days=ttl,
            oauth_clock_skew_seconds=clock_skew,
        )
        config.validate()
        return config

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("DASHBOARD_PUBLIC_BASE_URL", self.public_base_url),
                ("DASHBOARD_GOOGLE_OAUTH_CLIENT_ID", self.client_id),
                ("DASHBOARD_GOOGLE_OAUTH_CLIENT_SECRET", self.client_secret),
                ("DASHBOARD_ALLOWED_EMAIL_DOMAIN", self.allowed_domain),
            )
            if not value
        ]
        if missing:
            raise AuthError(
                "Missing dashboard authentication configuration: "
                + ", ".join(missing),
                "AUTH_CONFIG_ERROR",
            )
        parsed = urlsplit(self.public_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AuthError(
                "DASHBOARD_PUBLIC_BASE_URL must be an absolute HTTP(S) URL.",
                "AUTH_CONFIG_ERROR",
            )
        if not 1 <= self.session_ttl_days <= 30:
            raise AuthError(
                "DASHBOARD_SESSION_TTL_DAYS must be between 1 and 30.",
                "AUTH_CONFIG_ERROR",
            )
        if not 0 <= self.oauth_clock_skew_seconds <= 300:
            raise AuthError(
                "DASHBOARD_OAUTH_CLOCK_SKEW_SECONDS must be between 0 and 300.",
                "AUTH_CONFIG_ERROR",
            )

    @property
    def callback_url(self) -> str:
        return f"{self.public_base_url}/api/auth/google/callback"

    @property
    def secure_cookie(self) -> bool:
        return urlsplit(self.public_base_url).scheme == "https"


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_next_path(value: str | None) -> str:
    candidate = str(value or "/").strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    if "\\" in candidate or any(char in candidate for char in ("\r", "\n")):
        return "/"
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return "/"
    return urlunsplit(("", "", parsed.path or "/", parsed.query, ""))


class AuthRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def create_login_attempt(
        self,
        state: str,
        code_verifier: str,
        next_path: str,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM oauth_login_attempts "
                    "WHERE expires_at <= now()"
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO oauth_login_attempts (
                        state_hash, code_verifier, next_path, expires_at
                    ) VALUES (
                        :state_hash, :code_verifier, :next_path,
                        now() + (:ttl_seconds * interval '1 second')
                    )
                    """
                ),
                {
                    "state_hash": token_hash(state),
                    "code_verifier": code_verifier,
                    "next_path": safe_next_path(next_path),
                    "ttl_seconds": OAUTH_ATTEMPT_TTL_SECONDS,
                },
            )

    def consume_login_attempt(self, state: str) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    DELETE FROM oauth_login_attempts
                    WHERE state_hash = :state_hash
                    RETURNING code_verifier, next_path, expires_at
                    """
                ),
                {"state_hash": token_hash(state)},
            ).mappings().first()
        if not row:
            return None
        result = dict(row)
        expires_at = result.get("expires_at")
        if expires_at and expires_at <= datetime.now(timezone.utc):
            return None
        return result

    def upsert_user(self, claims: dict[str, Any]) -> dict[str, Any]:
        email = str(claims["email"]).strip()
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    INSERT INTO auth_users (
                        google_subject, email, email_normalized,
                        display_name, avatar_url, last_login_at
                    ) VALUES (
                        :google_subject, :email, :email_normalized,
                        :display_name, :avatar_url, now()
                    )
                    ON CONFLICT (google_subject) DO UPDATE SET
                        email = EXCLUDED.email,
                        email_normalized = EXCLUDED.email_normalized,
                        display_name = EXCLUDED.display_name,
                        avatar_url = EXCLUDED.avatar_url,
                        last_login_at = now(),
                        updated_at = now()
                    RETURNING id, email, display_name, avatar_url,
                              is_active, last_login_at
                    """
                ),
                {
                    "google_subject": str(claims["sub"]),
                    "email": email,
                    "email_normalized": email.lower(),
                    "display_name": str(claims.get("name") or email.split("@", 1)[0]),
                    "avatar_url": str(claims.get("picture") or "") or None,
                },
            ).mappings().one()
        return dict(row)

    def create_session(
        self,
        user_id: str,
        session_token: str,
        csrf_token: str,
        expires_at: datetime,
        user_agent: str | None,
    ) -> dict[str, Any]:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM auth_sessions "
                    "WHERE expires_at <= now() OR revoked_at IS NOT NULL"
                )
            )
            row = connection.execute(
                text(
                    """
                    INSERT INTO auth_sessions (
                        user_id, token_hash, csrf_token_hash,
                        user_agent, expires_at
                    ) VALUES (
                        :user_id, :token_hash, :csrf_token_hash,
                        :user_agent, :expires_at
                    )
                    RETURNING id, created_at, expires_at
                    """
                ),
                {
                    "user_id": user_id,
                    "token_hash": token_hash(session_token),
                    "csrf_token_hash": token_hash(csrf_token),
                    "user_agent": (user_agent or "")[:1000] or None,
                    "expires_at": expires_at,
                },
            ).mappings().one()
        return dict(row)

    def session(self, session_token: str) -> dict[str, Any] | None:
        if not session_token:
            return None
        hashed = token_hash(session_token)
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        s.id AS session_id,
                        s.csrf_token_hash,
                        s.created_at AS session_created_at,
                        s.expires_at,
                        u.id AS user_id,
                        u.google_subject,
                        u.email,
                        u.display_name,
                        u.avatar_url,
                        u.is_active
                    FROM auth_sessions s
                    JOIN auth_users u ON u.id = s.user_id
                    WHERE s.token_hash = :token_hash
                      AND s.revoked_at IS NULL
                      AND s.expires_at > now()
                      AND u.is_active = TRUE
                    """
                ),
                {"token_hash": hashed},
            ).mappings().first()
            if row:
                connection.execute(
                    text(
                        """
                        UPDATE auth_sessions
                        SET last_seen_at = now()
                        WHERE token_hash = :token_hash
                          AND last_seen_at < now() - interval '1 hour'
                        """
                    ),
                    {"token_hash": hashed},
                )
        return dict(row) if row else None

    def revoke_session(self, session_token: str) -> None:
        if not session_token:
            return
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = COALESCE(revoked_at, now())
                    WHERE token_hash = :token_hash
                    """
                ),
                {"token_hash": token_hash(session_token)},
            )


class GoogleOAuthService:
    authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint = "https://oauth2.googleapis.com/token"

    def __init__(self, engine: Engine):
        self.repository = AuthRepository(engine)

    def auth_mode(self) -> str:
        mode = str(os.getenv("DASHBOARD_AUTH_MODE") or "google").strip().lower()
        if mode not in AUTH_MODES:
            raise AuthError(
                "DASHBOARD_AUTH_MODE must be 'google', 'local', or 'disabled'.",
                "AUTH_CONFIG_ERROR",
            )
        return mode

    def _validate_local_mode(self) -> None:
        public_base_url = str(
            os.getenv("DASHBOARD_PUBLIC_BASE_URL") or "http://localhost:8000"
        ).strip().rstrip("/")
        parsed = urlsplit(public_base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_AUTH_HOSTS:
            raise AuthError(
                "Local authentication modes are only allowed for localhost development.",
                "AUTH_CONFIG_ERROR",
            )

    def local_auth_disabled(self) -> bool:
        if self.auth_mode() != "disabled":
            return False
        self._validate_local_mode()
        return True

    def local_login_enabled(self) -> bool:
        if self.auth_mode() != "local":
            return False
        self._validate_local_mode()
        return True

    def validate_runtime(self) -> None:
        retrieval_token = str(os.getenv("DASHBOARD_RETRIEVAL_TOKEN") or "").strip()
        if retrieval_token and len(retrieval_token) < 32:
            raise AuthError(
                "DASHBOARD_RETRIEVAL_TOKEN must contain at least 32 characters.",
                "AUTH_CONFIG_ERROR",
            )
        mode = self.auth_mode()
        if mode in {"local", "disabled"}:
            self._validate_local_mode()
            return
        self.config()

    def local_development_user(self) -> dict[str, Any] | None:
        if not self.local_auth_disabled():
            return None
        return {
            "id": "local-development",
            "email": "local@mai.co.id",
            "name": "Local Development",
            "picture": None,
            "local_auth_disabled": True,
        }

    def create_local_session(
        self,
        next_path: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        if not self.local_login_enabled():
            raise AuthError(
                "Local development login is not enabled.",
                "AUTH_MODE_NOT_AVAILABLE",
            )
        raw_ttl = str(os.getenv("DASHBOARD_SESSION_TTL_DAYS") or "7").strip()
        try:
            ttl_days = int(raw_ttl)
        except ValueError as exc:
            raise AuthError(
                "DASHBOARD_SESSION_TTL_DAYS must be an integer.",
                "AUTH_CONFIG_ERROR",
            ) from exc
        if not 1 <= ttl_days <= 30:
            raise AuthError(
                "DASHBOARD_SESSION_TTL_DAYS must be between 1 and 30.",
                "AUTH_CONFIG_ERROR",
            )
        user = self.repository.upsert_user(
            {
                "sub": "local-development",
                "email": "local@mai.co.id",
                "name": "Local Development",
                "picture": None,
            }
        )
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        session = self.repository.create_session(
            str(user["id"]),
            session_token,
            csrf_token,
            expires_at,
            user_agent,
        )
        return {
            "user": user,
            "session": session,
            "session_token": session_token,
            "csrf_token": csrf_token,
            "next_path": safe_next_path(next_path),
            "expires_at": expires_at,
            "session_ttl_days": ttl_days,
        }

    def config(self) -> AuthConfig:
        return AuthConfig.from_env()

    def begin_login(self, next_path: str | None) -> tuple[str, str]:
        config = self.config()
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        destination = safe_next_path(next_path)
        self.repository.create_login_attempt(state, verifier, destination)
        query = urlencode(
            {
                "client_id": config.client_id,
                "redirect_uri": config.callback_url,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "hd": config.allowed_domain,
                "prompt": "select_account",
            }
        )
        return f"{self.authorization_endpoint}?{query}", state

    def complete_login(
        self,
        code: str | None,
        state: str | None,
        state_cookie: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        if not code:
            raise AuthError("Google did not return an authorization code.", "OAUTH_CALLBACK_ERROR")
        if not state or not state_cookie or not hmac.compare_digest(state, state_cookie):
            raise AuthError("The login request could not be verified.", "OAUTH_STATE_INVALID")
        attempt = self.repository.consume_login_attempt(state)
        if not attempt:
            raise AuthError("The login request has expired or was already used.", "OAUTH_STATE_EXPIRED")

        config = self.config()
        try:
            response = requests.post(
                self.token_endpoint,
                data={
                    "code": code,
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "redirect_uri": config.callback_url,
                    "grant_type": "authorization_code",
                    "code_verifier": attempt["code_verifier"],
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning(
                "Google OAuth token endpoint request failed (%s).",
                type(exc).__name__,
            )
            raise AuthError(
                "Google could not be reached to complete login.",
                "OAUTH_TOKEN_EXCHANGE_FAILED",
            ) from exc

        if not response.ok:
            try:
                google_error = str(response.json().get("error") or "unknown_error")
            except (TypeError, ValueError):
                google_error = "invalid_response"
            logger.warning(
                "Google OAuth token exchange rejected: status=%s error=%s.",
                response.status_code,
                google_error[:80],
            )
            raise AuthError(
                "Google rejected the login code exchange.",
                "OAUTH_TOKEN_EXCHANGE_FAILED",
            )

        try:
            token_payload = response.json()
            raw_id_token = token_payload.get("id_token")
        except (TypeError, ValueError) as exc:
            logger.warning("Google OAuth token endpoint returned invalid JSON.")
            raise AuthError(
                "Google returned an invalid login response.",
                "OAUTH_TOKEN_EXCHANGE_FAILED",
            ) from exc
        if not raw_id_token:
            logger.warning("Google OAuth token response did not include an ID token.")
            raise AuthError(
                "Google did not return an identity token.",
                "OAUTH_ID_TOKEN_INVALID",
            )

        try:
            claims = google_id_token.verify_oauth2_token(
                raw_id_token,
                GoogleAuthRequest(),
                config.client_id,
                clock_skew_in_seconds=config.oauth_clock_skew_seconds,
            )
        except Exception as exc:
            verification_detail = " ".join(str(exc).split())[:300]
            logger.warning(
                "Google OAuth ID token verification failed (%s): %s",
                type(exc).__name__,
                verification_detail or "no detail",
            )
            raise AuthError(
                "Google identity token could not be verified.",
                "OAUTH_ID_TOKEN_INVALID",
            ) from exc

        issuer = str(claims.get("iss") or "")
        email = str(claims.get("email") or "").strip()
        email_domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
        hosted_domain = str(claims.get("hd") or "").lower()
        verified = claims.get("email_verified") is True or str(
            claims.get("email_verified")
        ).lower() == "true"
        if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
            raise AuthError("The Google token issuer is invalid.", "OAUTH_TOKEN_INVALID")
        if not verified:
            raise AuthError("Your Google email address is not verified.", "EMAIL_NOT_VERIFIED")
        if email_domain != config.allowed_domain or hosted_domain != config.allowed_domain:
            raise AuthError(
                f"Only @{config.allowed_domain} accounts can access this dashboard.",
                "DOMAIN_NOT_ALLOWED",
            )
        if not claims.get("sub"):
            raise AuthError("The Google account identifier is missing.", "OAUTH_TOKEN_INVALID")

        try:
            user = self.repository.upsert_user(claims)
        except Exception as exc:
            raise AuthError(
                "This email is already linked to a different Google identity.",
                "ACCOUNT_CONFLICT",
            ) from exc
        if not user.get("is_active"):
            raise AuthError("This dashboard account has been disabled.", "ACCOUNT_DISABLED")

        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=config.session_ttl_days
        )
        session = self.repository.create_session(
            str(user["id"]),
            session_token,
            csrf_token,
            expires_at,
            user_agent,
        )
        return {
            "user": user,
            "session": session,
            "session_token": session_token,
            "csrf_token": csrf_token,
            "next_path": safe_next_path(attempt.get("next_path")),
            "expires_at": expires_at,
        }

    def current_session(self, session_token: str | None) -> dict[str, Any] | None:
        session = self.repository.session(str(session_token or ""))
        if session and self.auth_mode() == "google":
            if session.get("google_subject") == "local-development":
                return None
            domain = str(session.get("email") or "").rsplit("@", 1)[-1].lower()
            if domain != self.config().allowed_domain:
                return None
        return session

    def retrieval_authenticated(self, authorization: str | None) -> bool:
        expected = str(os.getenv("DASHBOARD_RETRIEVAL_TOKEN") or "").strip()
        if len(expected) < 32 or not authorization:
            return False
        scheme, _, token = authorization.partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(
            token.encode("utf-8"), expected.encode("utf-8")
        )

    def validate_csrf(self, session: dict[str, Any], csrf_token: str | None) -> bool:
        if not csrf_token:
            return False
        expected = str(session.get("csrf_token_hash") or "")
        return bool(expected) and hmac.compare_digest(expected, token_hash(csrf_token))

    def revoke(self, session_token: str | None) -> None:
        self.repository.revoke_session(str(session_token or ""))
