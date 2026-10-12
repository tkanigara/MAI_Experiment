import loginBuilding from "../assets/login-building.png";
import maiLogo from "../assets/logo-mai.svg";
import { useState } from "react";
import { api } from "../lib/api";

const ERROR_MESSAGES = {
  domain_not_allowed: "Please use your company Google account with an @mai.co.id email address.",
  email_not_verified: "Your Google email address has not been verified.",
  account_disabled: "Your dashboard account has been disabled. Please contact your administrator.",
  account_conflict: "This email address is already linked to a different Google account.",
  oauth_cancelled: "Sign-in was cancelled. Please try again.",
  oauth_callback_error: "Google did not return the information needed to sign you in. Please try again.",
  oauth_state_invalid: "Your sign-in request could not be verified. Please start again.",
  oauth_state_expired: "Your sign-in request has expired. Please try again.",
  oauth_token_invalid: "Your Google sign-in could not be verified. Please try again.",
  oauth_token_exchange_failed: "We could not complete your Google sign-in. Please try again or contact your administrator.",
  oauth_id_token_invalid: "Your Google account could not be verified. Please try again.",
  auth_unavailable: "The sign-in service is temporarily unavailable. Please try again later.",
};

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="google-icon">
      <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.4-.18-2.07H12v3.92h5.38a4.6 4.6 0 0 1-2 3.02v2.54h3.24c1.9-1.75 2.98-4.33 2.98-7.41Z" />
      <path fill="#34A853" d="M12 22c2.7 0 4.97-.9 6.62-2.36l-3.24-2.54c-.9.6-2.05.96-3.38.96-2.61 0-4.82-1.76-5.61-4.13H3.04v2.62A10 10 0 0 0 12 22Z" />
      <path fill="#FBBC05" d="M6.39 13.93A6.02 6.02 0 0 1 6.07 12c0-.67.12-1.32.32-1.93V7.45H3.04A10 10 0 0 0 2 12c0 1.61.38 3.14 1.04 4.55l3.35-2.62Z" />
      <path fill="#EA4335" d="M12 5.94c1.47 0 2.79.5 3.83 1.5l2.87-2.88A9.62 9.62 0 0 0 12 2a10 10 0 0 0-8.96 5.45l3.35 2.62C7.18 7.7 9.39 5.94 12 5.94Z" />
    </svg>
  );
}

export default function LoginPage({ authMode = "google", errorCode, nextPath }) {
  const [localError, setLocalError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const message = errorCode ? ERROR_MESSAGES[errorCode] || "Sign-in failed. Please try again." : "";
  const startLogin = async () => {
    const next = nextPath && nextPath.startsWith("/") && !nextPath.startsWith("//")
      ? nextPath
      : "/";
    if (authMode === "local") {
      setIsSubmitting(true);
      setLocalError("");
      try {
        const result = await api("/api/auth/local/login", {
          method: "POST",
          body: JSON.stringify({ next_path: next }),
          skipAuthRedirect: true,
        });
        window.location.assign(result.next_path || "/");
      } catch (error) {
        setLocalError(error.message || "Local sign-in failed. Please try again.");
        setIsSubmitting(false);
      }
      return;
    }
    window.location.assign(`/api/auth/google/start?next=${encodeURIComponent(next)}`);
  };

  const isLocal = authMode === "local";

  return (
    <main className="login-page">
      <section className="login-cover" aria-label="MAI office building">
        <img src={loginBuilding} alt="Modern office building" />
        <div className="login-cover-overlay" />
        <div className="login-cover-copy">
          <span className="login-cover-eyebrow">MAHAKARYA ADI INDONESIA</span>
          <h1>Reporting, insights, and performance in one workspace.</h1>
          <p>Manage Social Media and Ads reports in one integrated dashboard.</p>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <img className="login-brand-logo" src={maiLogo} alt="Mahakarya Adi Indonesia" />
          <p className="login-kicker">MAI REPORTING DASHBOARD</p>
          <h2>Welcome back</h2>
          <p className="login-description">
            {isLocal
              ? "Sign in with a development session to test the local sign-in flow."
              : "Sign in with your company Google account to continue."}
          </p>
          {message && <div className="login-error" role="alert">{message}</div>}
          {localError && <div className="login-error" role="alert">{localError}</div>}
          <button className="google-login-button" type="button" onClick={startLogin} disabled={isSubmitting}>
            {!isLocal && <GoogleIcon />}
            <span>{isSubmitting ? "Signing in..." : isLocal ? "Continue as Local Developer" : "Continue with Google"}</span>
          </button>
          <p className="login-domain-note">
            {isLocal
              ? "Local testing mode · available on localhost only."
              : <>Only accounts with an <strong>@mai.co.id</strong> email address can access this dashboard.</>}
          </p>
        </div>
        <p className="login-footer">Mahakarya Adi Indonesia · Internal Workspace</p>
      </section>
    </main>
  );
}
