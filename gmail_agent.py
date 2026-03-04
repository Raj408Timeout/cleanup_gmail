"""
Gmail Agent - Step-by-step interactive agent to read, search, and delete emails
Built for VS Code + Claude Desktop integration

SETUP STEPS (run once):
    pip install -r requirements.txt
    → Then follow the auth flow when you run this script
"""

import os
import base64
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

# Scopes determine what the agent can do with Gmail
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",   # Read & list emails
    "https://www.googleapis.com/auth/gmail.modify",     # Delete/trash emails
]

CREDENTIALS_FILE = "credentials.json"   # Downloaded from Google Cloud Console
TOKEN_FILE = "token.json"               # Auto-created after first login


# ─────────────────────────────────────────────
# STEP 1: AUTHENTICATION
# ─────────────────────────────────────────────

def authenticate():
    """
    Authenticates with Gmail via OAuth2.
    - First run: opens a browser for Google login → saves token.json
    - Subsequent runs: uses saved token (refreshes if expired)
    """
    creds = None

    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid credentials, trigger login flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🔐 Opening browser for Google login...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future runs
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        print("✅ Authentication successful! Token saved.\n")

    return build("gmail", "v1", credentials=creds)


# ─────────────────────────────────────────────
# STEP 2: LIST EMAILS
# ─────────────────────────────────────────────

def list_emails(service, max_results=10, label="INBOX"):
    """
    Lists recent emails from your inbox (or any label).
    Returns a list of simplified email dicts.
    """
    print(f"\n📬 Fetching last {max_results} emails from {label}...\n")

    results = service.users().messages().list(
        userId="me",
        labelIds=[label],
        maxResults=max_results
    ).execute()

    messages = results.get("messages", [])

    if not messages:
        print("📭 No emails found.")
        return []

    emails = []
    for msg in messages:
        email = get_email_detail(service, msg["id"])
        emails.append(email)
        print(f"  [{len(emails)}] 📧 From: {email['from']}")
        print(f"       Subject: {email['subject']}")
        print(f"       Date: {email['date']}")
        print(f"       ID: {email['id']}\n")

    return emails


# ─────────────────────────────────────────────
# STEP 3: GET EMAIL DETAIL
# ─────────────────────────────────────────────

def get_email_detail(service, message_id):
    """
    Fetches full details of a single email by ID.
    Extracts: From, Subject, Date, and plain-text body snippet.
    """
    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}

    body = extract_body(msg["payload"])

    return {
        "id": message_id,
        "from": headers.get("From", "Unknown"),
        "subject": headers.get("Subject", "(no subject)"),
        "date": headers.get("Date", "Unknown"),
        "snippet": msg.get("snippet", ""),
        "body": body
    }


def extract_body(payload):
    """Recursively extracts plain text body from email payload."""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            elif "parts" in part:
                return extract_body(part)
    elif payload.get("mimeType") == "text/plain":
        data = payload["body"].get("data", "")
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return "(no plain text body)"


# ─────────────────────────────────────────────
# STEP 4: SEARCH EMAILS
# ─────────────────────────────────────────────

def search_emails(service, query, max_results=10):
    """
    Searches emails using Gmail's search syntax.
    Examples:
        "from:boss@company.com"
        "subject:invoice is:unread"
        "after:2024/01/01 has:attachment"
        "is:unread label:INBOX"
    """
    print(f"\n🔍 Searching: '{query}'...\n")

    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results
    ).execute()

    messages = results.get("messages", [])

    if not messages:
        print("❌ No emails matched your search.")
        return []

    print(f"✅ Found {len(messages)} result(s):\n")
    emails = []
    for msg in messages:
        email = get_email_detail(service, msg["id"])
        emails.append(email)
        print(f"  [{len(emails)}] 📧 From: {email['from']}")
        print(f"       Subject: {email['subject']}")
        print(f"       Date: {email['date']}")
        print(f"       ID: {email['id']}\n")

    return emails


# ─────────────────────────────────────────────
# STEP 5: DELETE (TRASH) EMAILS
# ─────────────────────────────────────────────

def trash_email(service, message_id):
    """
    Moves an email to Trash (recoverable for 30 days).
    Safer than permanent delete.
    """
    service.users().messages().trash(userId="me", id=message_id).execute()
    print(f"🗑️  Email {message_id} moved to Trash.")


def delete_email_permanently(service, message_id):
    """
    Permanently deletes an email. Cannot be undone.
    Use with caution!
    """
    service.users().messages().delete(userId="me", id=message_id).execute()
    print(f"💥 Email {message_id} permanently deleted.")


# ─────────────────────────────────────────────
# STEP 6: INTERACTIVE AGENT LOOP
# ─────────────────────────────────────────────

def run_agent():
    """
    Main interactive agent loop.
    Authenticates once, then lets you run commands interactively.
    """
    print("=" * 55)
    print("  📮 Gmail Agent — VS Code Edition")
    print("=" * 55)

    # Authenticate and build service
    service = authenticate()
    print("✅ Connected to Gmail!\n")

    last_emails = []  # Store last search/list result for quick reference

    while True:
        print("\nWhat would you like to do?")
        print("  [1] List inbox emails")
        print("  [2] Search emails")
        print("  [3] Read full email")
        print("  [4] Trash an email (move to trash)")
        print("  [5] Permanently delete an email")
        print("  [q] Quit")
        print()

        choice = input("👉 Enter choice: ").strip().lower()

        # ── LIST ──────────────────────────────
        if choice == "1":
            n = input("How many emails to fetch? (default 10): ").strip()
            n = int(n) if n.isdigit() else 10
            last_emails = list_emails(service, max_results=n)

        # ── SEARCH ────────────────────────────
        elif choice == "2":
            print("\nGmail search tips:")
            print("  from:someone@email.com | subject:invoice | is:unread | has:attachment")
            query = input("\n🔍 Enter search query: ").strip()
            if query:
                last_emails = search_emails(service, query)

        # ── READ ──────────────────────────────
        elif choice == "3":
            if last_emails:
                print("\nWhich email? Enter the number from the last list, or paste an ID.")
                ref = input("📨 Email # or ID: ").strip()
                if ref.isdigit() and 1 <= int(ref) <= len(last_emails):
                    email = last_emails[int(ref) - 1]
                else:
                    email = get_email_detail(service, ref)

                print("\n" + "─" * 50)
                print(f"From:    {email['from']}")
                print(f"Subject: {email['subject']}")
                print(f"Date:    {email['date']}")
                print("─" * 50)
                print(email["body"] or email["snippet"])
                print("─" * 50)
            else:
                print("⚠️  No emails loaded yet. List or search first.")

        # ── TRASH ─────────────────────────────
        elif choice == "4":
            ref = input("🗑️  Enter email # or ID to trash: ").strip()
            if ref.isdigit() and last_emails and 1 <= int(ref) <= len(last_emails):
                msg_id = last_emails[int(ref) - 1]["id"]
            else:
                msg_id = ref
            confirm = input(f"Trash email {msg_id}? (y/n): ").strip().lower()
            if confirm == "y":
                trash_email(service, msg_id)

        # ── DELETE ────────────────────────────
        elif choice == "5":
            ref = input("💥 Enter email # or ID to PERMANENTLY delete: ").strip()
            if ref.isdigit() and last_emails and 1 <= int(ref) <= len(last_emails):
                msg_id = last_emails[int(ref) - 1]["id"]
            else:
                msg_id = ref
            confirm = input(f"⚠️  PERMANENTLY delete {msg_id}? This cannot be undone! (yes/n): ").strip().lower()
            if confirm == "yes":
                delete_email_permanently(service, msg_id)

        # ── QUIT ──────────────────────────────
        elif choice == "q":
            print("\n👋 Goodbye!")
            break

        else:
            print("❓ Invalid choice. Please enter 1–5 or q.")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    run_agent()