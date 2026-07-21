import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

from generate_slides_example import SCOPES


def main():
    parser = argparse.ArgumentParser(
        description="Create a fresh OAuth token for Google Slides report generation."
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the authorization URL instead of opening it automatically.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    load_dotenv(project_root / ".env")

    credentials_path = project_root / os.getenv(
        "GOOGLE_CREDENTIALS_FILE", "credentials.json"
    )
    token_path = project_root / os.getenv("GOOGLE_TOKEN_FILE", "token.json")
    oauth_port = int(os.getenv("GOOGLE_OAUTH_PORT", "0"))

    if not credentials_path.exists():
        raise FileNotFoundError(f"Google credentials file not found: {credentials_path}")

    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    credentials = flow.run_local_server(
        port=oauth_port,
        open_browser=not args.no_browser,
    )
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Google OAuth token created: {token_path.name}")


if __name__ == "__main__":
    main()
