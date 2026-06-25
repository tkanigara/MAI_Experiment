import os
from pathlib import Path

from google.oauth2 import service_account


def _secret_resource_name(secret_id, project_id=None, version="latest"):
    if secret_id.startswith("projects/"):
        if "/versions/" in secret_id:
            return secret_id
        return f"{secret_id}/versions/{version}"

    project = (
        project_id
        or os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        or os.environ.get("GCP_PROJECT", "").strip()
        or os.environ.get("SECRET_MANAGER_PROJECT_ID", "").strip()
    )
    if not project:
        raise RuntimeError(
            "Set SECRET_MANAGER_PROJECT_ID or use a full secret resource name."
        )
    return f"projects/{project}/secrets/{secret_id}/versions/{version}"


def _credentials_from_env():
    credentials_path = (
        os.environ.get("SECRET_MANAGER_SERVICE_ACCOUNT_FILE", "").strip()
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    )
    if not credentials_path:
        return None

    path = Path(credentials_path)
    if path.exists():
        return service_account.Credentials.from_service_account_file(
            str(path),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    return None


def access_secret(secret_id, project_id=None, version="latest"):
    try:
        from google.cloud import secretmanager
    except ImportError as exc:
        raise RuntimeError(
            "Install google-cloud-secret-manager to read secrets from Secret Manager."
        ) from exc

    client = secretmanager.SecretManagerServiceClient(
        credentials=_credentials_from_env(),
        transport="rest",
    )
    name = _secret_resource_name(secret_id, project_id=project_id, version=version)
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8").strip()


def hydrate_env_from_secret(env_name):
    if os.environ.get(env_name, "").strip():
        return

    secret_id = os.environ.get(f"{env_name}_SECRET_ID", "").strip()
    if not secret_id:
        return

    project_id = os.environ.get(f"{env_name}_SECRET_PROJECT_ID", "").strip() or None
    version = os.environ.get(f"{env_name}_SECRET_VERSION", "latest").strip() or "latest"
    try:
        os.environ[env_name] = access_secret(
            secret_id,
            project_id=project_id,
            version=version,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load {env_name} from Google Secret Manager secret "
            f"{secret_id!r}: {exc}"
        ) from exc
