"""
One-time Google OAuth2 setup script.
Run: venv/bin/python setup_google_auth.py
Sign in as sanath.anantha08@gmail.com when the browser opens.
"""
import json
import os
import sys

CREDENTIALS_FILE = "google_credentials.json"
TOKEN_FILE       = "google_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]


def main():
    print("Starting Google OAuth2 setup...")

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"\nERROR: '{CREDENTIALS_FILE}' not found in current directory.")
        print(f"Current directory: {os.getcwd()}")
        sys.exit(1)

    print(f"Found credentials file: {CREDENTIALS_FILE}")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("\nERROR: google_auth_oauthlib not installed.")
        print("Run: venv/bin/pip install google-auth-oauthlib")
        sys.exit(1)

    print("Opening browser for authorization...")
    print("Sign in as sanath.anantha08@gmail.com and click Allow.\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
    except Exception as e:
        print(f"\nERROR during OAuth flow: {e}")
        sys.exit(1)

    print("Authorization successful! Saving token...")

    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes) if creds.scopes else SCOPES,
        "expiry":        creds.expiry.isoformat() if creds.expiry else None,
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"\nDone! Token saved to: {os.path.abspath(TOKEN_FILE)}")
    print(f"Make sure your .env has:  GOOGLE_TOKEN_PATH=./{TOKEN_FILE}")


if __name__ == "__main__":
    main()
