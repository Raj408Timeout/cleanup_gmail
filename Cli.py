"""
Gmail Cleanup CLI
─────────────────
Interactive command-line agent to preview, filter, and delete Gmail emails.
Reuses auth and Gmail logic from gmail_bulk_delete.py and gmail_mcp_server.py.

Install dependencies:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Run:
    python cli.py
"""

import os
import time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE       = os.path.join(BASE_DIR, "token.json")
SCOPES           = ["https://mail.google.com/"]
BATCH_SIZE       = 500

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing token...")
            creds.refresh(Request())
        else:
            print("🌐 Launching OAuth flow — browser will open...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("✅ Token saved.\n")
    return creds

# ─────────────────────────────────────────────
# GMAIL HELPERS
# ─────────────────────────────────────────────

def get_all_message_ids(service, query):
    print(f"\n🔍 Searching for: {query}")
    message_ids = []
    page_token = None
    while True:
        result = service.users().messages().list(
            userId="me", q=query, maxResults=500, pageToken=page_token
        ).execute()
        messages = result.get("messages", [])
        message_ids.extend([m["id"] for m in messages])
        print(f"   Found {len(message_ids)} emails so far...", end="\r")
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    print(f"\n   Total: {len(message_ids)} emails found.")
    return message_ids


def preview_emails(service, message_ids, limit=10):
    print(f"\n📋 Previewing first {min(limit, len(message_ids))} email(s):\n")
    print(f"  {'#':<4} {'From':<35} {'Subject':<45} {'Date':<20}")
    print("  " + "─" * 104)
    for i, msg_id in enumerate(message_ids[:limit], 1):
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        frm     = headers.get("From", "Unknown")[:33]
        subject = headers.get("Subject", "(no subject)")[:43]
        date    = headers.get("Date", "Unknown")[:18]
        print(f"  {i:<4} {frm:<35} {subject:<45} {date:<20}")
    if len(message_ids) > limit:
        print(f"\n  ... and {len(message_ids) - limit} more emails.")


def batch_delete(service, message_ids, dry_run=False):
    total = len(message_ids)
    deleted = 0
    for i in range(0, total, BATCH_SIZE):
        batch = message_ids[i:i + BATCH_SIZE]
        label = "[DRY RUN] Would delete" if dry_run else "Deleting"
        print(f"  {label} batch {i // BATCH_SIZE + 1} ({len(batch)} emails)...", end=" ")
        if not dry_run:
            service.users().messages().batchDelete(
                userId="me", body={"ids": batch}
            ).execute()
            time.sleep(0.5)
        deleted += len(batch)
        status = "(skipped)" if dry_run else "✓"
        print(f"{status} ({deleted}/{total})")
    return deleted


def batch_trash(service, message_ids, dry_run=False):
    total = len(message_ids)
    trashed = 0
    for i, msg_id in enumerate(message_ids, 1):
        label = "[DRY RUN] Would trash" if dry_run else "Trashing"
        print(f"  {label} email {i}/{total}...", end="\r")
        if not dry_run:
            service.users().messages().trash(userId="me", id=msg_id).execute()
            if i % 50 == 0:
                time.sleep(0.5)
        trashed += 1
    print()
    return trashed

# ─────────────────────────────────────────────
# FILTER BUILDER (interactive)
# ─────────────────────────────────────────────

def build_query_interactive():
    print("\n─────────────────────────────────────")
    print("  🔧 Build your email filter")
    print("─────────────────────────────────────")

    parts = []

    # Category / Label
    print("\n[1] Category or Label")
    print("  1) Promotions    2) Social    3) Updates    4) Inbox    5) Custom    6) Skip")
    choice = input("  Choose: ").strip()
    category_map = {
        "1": "category:promotions",
        "2": "category:social",
        "3": "category:updates",
        "4": "in:inbox",
    }
    if choice in category_map:
        parts.append(category_map[choice])
    elif choice == "5":
        custom = input("  Enter label/category query (e.g. label:newsletters): ").strip()
        if custom:
            parts.append(custom)

    # Sender
    print("\n[2] Filter by sender (press Enter to skip)")
    sender = input("  From email address: ").strip()
    if sender:
        parts.append(f"from:{sender}")

    # Date range
    print("\n[3] Date range (press Enter to skip each)")
    after = input("  After date (YYYY/MM/DD): ").strip()
    if after:
        parts.append(f"after:{after}")
    before = input("  Before date (YYYY/MM/DD): ").strip()
    if before:
        parts.append(f"before:{before}")

    # Subject keyword
    print("\n[4] Subject keyword (press Enter to skip)")
    keyword = input("  Subject contains: ").strip()
    if keyword:
        parts.append(f"subject:{keyword}")

    if not parts:
        print("\n⚠️  No filters set. This will match ALL emails.")
        confirm = input("  Continue anyway? (yes/no): ").strip().lower()
        if confirm != "yes":
            return None
        return "in:inbox"

    query = " ".join(parts)
    print(f"\n  ✅ Query: {query}")
    return query

# ─────────────────────────────────────────────
# MAIN CLI
# ─────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════╗")
    print("║     📧 Gmail Cleanup CLI         ║")
    print("╚══════════════════════════════════╝\n")

    # Auth
    creds   = authenticate()
    service = build("gmail", "v1", credentials=creds)
    print("✅ Connected to Gmail.\n")

    while True:
        print("\n─────────────────────────────────────")
        print("  Main Menu")
        print("─────────────────────────────────────")
        print("  1) Search & preview emails")
        print("  2) Search & delete emails (permanent)")
        print("  3) Search & trash emails (recoverable)")
        print("  4) Dry run (simulate delete, no changes)")
        print("  5) Exit")
        choice = input("\nChoose an option: ").strip()

        if choice == "5":
            print("\n👋 Goodbye!\n")
            break

        if choice not in ("1", "2", "3", "4"):
            print("❌ Invalid option.")
            continue

        # Build query
        query = build_query_interactive()
        if not query:
            continue

        # Fetch matching emails
        message_ids = get_all_message_ids(service, query)
        if not message_ids:
            print("\n📭 No emails matched your filter.")
            continue

        # Always preview first
        preview_emails(service, message_ids, limit=10)

        if choice == "1":
            input("\n  Press Enter to return to menu...")
            continue

        # Dry run
        if choice == "4":
            print(f"\n🧪 DRY RUN — {len(message_ids)} emails would be permanently deleted.")
            batch_delete(service, message_ids, dry_run=True)
            input("\n  Press Enter to return to menu...")
            continue

        # Confirm action
        action = "permanently DELETE" if choice == "2" else "TRASH"
        print(f"\n⚠️  About to {action} {len(message_ids)} emails.")
        if choice == "2":
            print("   This CANNOT be undone!")
        confirm = input("  Type 'yes' to confirm: ").strip().lower()
        if confirm != "yes":
            print("  Aborted.")
            continue

        print()
        if choice == "2":
            total = batch_delete(service, message_ids)
            print(f"\n✅ Done! {total} emails permanently deleted.")
        elif choice == "3":
            total = batch_trash(service, message_ids)
            print(f"\n✅ Done! {total} emails moved to Trash.")

if __name__ == "__main__":
    main()