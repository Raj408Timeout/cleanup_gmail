"""
Gmail Bulk Delete - 2024 Promotional Emails
-------------------------------------------
Deletes all emails in the Promotions category from 2024.
Place this script in the same folder as your credentials.json and token.json.

Install dependencies:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Run:
    python gmail_bulk_delete.py
"""

import os
import time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- Config ---
SCOPES = ['https://mail.google.com/']  # Full access needed for delete
CREDENTIALS_FILE = 'credentials.json'  # Same folder as this script
TOKEN_FILE = 'token.json'
QUERY = 'category:promotions after:2025/01/01 before:2026/01/01'
BATCH_SIZE = 500  # Gmail API batch delete limit
# --------------

def authenticate():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Refresh or re-authenticate if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing token...")
            creds.refresh(Request())
        else:
            print("Launching OAuth flow — browser will open...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save updated token
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
        print("Token saved.")

    return creds


def get_all_message_ids(service, query):
    """Fetch all message IDs matching the query."""
    print(f"\nSearching for: {query}")
    message_ids = []
    page_token = None

    while True:
        result = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=500,
            pageToken=page_token
        ).execute()

        messages = result.get('messages', [])
        message_ids.extend([m['id'] for m in messages])
        print(f"  Found {len(message_ids)} emails so far...", end='\r')

        page_token = result.get('nextPageToken')
        if not page_token:
            break

    print(f"\n  Total found: {len(message_ids)} emails")
    return message_ids


def batch_delete(service, message_ids):
    """Delete messages in batches of BATCH_SIZE."""
    total = len(message_ids)
    deleted = 0

    for i in range(0, total, BATCH_SIZE):
        batch = message_ids[i:i + BATCH_SIZE]
        print(f"Deleting batch {i // BATCH_SIZE + 1} ({len(batch)} emails)...", end=' ')

        service.users().messages().batchDelete(
            userId='me',
            body={'ids': batch}
        ).execute()

        deleted += len(batch)
        print(f"Done. ({deleted}/{total} total deleted)")
        time.sleep(0.5)  # Avoid rate limiting

    return deleted


def main():
    print("=== Gmail Bulk Delete: 2024 Promotions ===\n")

    # Authenticate
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)

    # Fetch all matching IDs
    message_ids = get_all_message_ids(service, QUERY)

    if not message_ids:
        print("\nNo emails found matching the query. Nothing to delete.")
        return

    # Confirm before deleting
    print(f"\n⚠️  About to PERMANENTLY DELETE {len(message_ids)} emails.")
    confirm = input("Type 'yes' to confirm: ").strip().lower()

    if confirm != 'yes':
        print("Aborted.")
        return

    # Delete in batches
    print()
    total_deleted = batch_delete(service, message_ids)
    print(f"\n✅ Done! {total_deleted} promotional emails from 2024 permanently deleted.")


if __name__ == '__main__':
    main()