"""
Gmail MCP Server
────────────────
Exposes Gmail tools to Claude Desktop via the MCP protocol.
Claude can then list, search, read, trash, and delete emails
directly from the chat window — no browser/localhost needed.

SETUP:
    pip install -r requirements.txt
    → Add config to claude_desktop_config.json (see README_MCP.md)
    → Restart Claude Desktop
    → Ask Claude: "show my inbox"
"""

import asyncio
import base64
import os
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ─────────────────────────────────────────────
# PATHS  — keep credentials next to this file
# ─────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE       = os.path.join(BASE_DIR, "token.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def extract_body(payload):
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            elif "parts" in part:
                result = extract_body(part)
                if result:
                    return result
    elif payload.get("mimeType") == "text/plain":
        data = payload["body"].get("data", "")
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


def format_email(msg, include_body=False):
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    result = {
        "id":      msg["id"],
        "from":    headers.get("From", "Unknown"),
        "subject": headers.get("Subject", "(no subject)"),
        "date":    headers.get("Date", "Unknown"),
        "snippet": msg.get("snippet", ""),
    }
    if include_body:
        result["body"] = extract_body(msg["payload"]) or msg.get("snippet", "")
    return result


# ─────────────────────────────────────────────
# MCP SERVER
# ─────────────────────────────────────────────

server = Server("gmail-agent")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_emails",
            description="List recent emails from Gmail inbox",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Number of emails to fetch (default 10)",
                        "default": 10
                    },
                    "label": {
                        "type": "string",
                        "description": "Gmail label to list from (default INBOX)",
                        "default": "INBOX"
                    }
                }
            }
        ),
        types.Tool(
            name="search_emails",
            description=(
                "Search Gmail using Gmail query syntax. "
                "Examples: 'from:boss@company.com', 'subject:invoice is:unread', "
                "'has:attachment after:2024/01/01'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max number of results (default 10)",
                        "default": 1000
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="read_email",
            description="Read the full body of an email by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Gmail message ID"
                    }
                },
                "required": ["email_id"]
            }
        ),
        types.Tool(
            name="trash_email",
            description="Move an email to Trash (recoverable for 30 days)",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Gmail message ID to trash"
                    }
                },
                "required": ["email_id"]
            }
        ),
        types.Tool(
            name="delete_email",
            description="Permanently delete an email. Cannot be undone. Always confirm with user first.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Gmail message ID to permanently delete"
                    }
                },
                "required": ["email_id"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    svc = get_gmail_service()

    # ── LIST EMAILS ───────────────────────────────────────────
    if name == "list_emails":
        max_results = arguments.get("max_results", 1000)
        label       = arguments.get("label", "INBOX")

        results  = svc.users().messages().list(
            userId="me", labelIds=[label], maxResults=max_results
        ).execute()
        messages = results.get("messages", [])

        if not messages:
            return [types.TextContent(type="text", text="📭 No emails found.")]

        emails = []
        for m in messages:
            full = svc.users().messages().get(
                userId="me", id=m["id"], format="full"
            ).execute()
            emails.append(format_email(full))

        lines = [f"📬 **{len(emails)} emails** from {label}:\n"]
        for i, e in enumerate(emails, 1):
            lines.append(
                f"{i}. **{e['subject']}**\n"
                f"   From: {e['from']}\n"
                f"   Date: {e['date']}\n"
                f"   ID: `{e['id']}`\n"
                f"   Preview: {e['snippet'][:80]}...\n"
            )
        return [types.TextContent(type="text", text="\n".join(lines))]

    # ── SEARCH EMAILS ─────────────────────────────────────────
    elif name == "search_emails":
        query       = arguments["query"]
        max_results = arguments.get("max_results", 1000)

        results  = svc.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = results.get("messages", [])

        if not messages:
            return [types.TextContent(type="text", text=f"❌ No emails found for: `{query}`")]

        emails = []
        for m in messages:
            full = svc.users().messages().get(
                userId="me", id=m["id"], format="full"
            ).execute()
            emails.append(format_email(full))

        lines = [f"🔍 **{len(emails)} result(s)** for `{query}`:\n"]
        for i, e in enumerate(emails, 1):
            lines.append(
                f"{i}. **{e['subject']}**\n"
                f"   From: {e['from']}\n"
                f"   Date: {e['date']}\n"
                f"   ID: `{e['id']}`\n"
                f"   Preview: {e['snippet'][:80]}...\n"
            )
        return [types.TextContent(type="text", text="\n".join(lines))]

    # ── READ EMAIL ────────────────────────────────────────────
    elif name == "read_email":
        email_id = arguments["email_id"]
        msg      = svc.users().messages().get(
            userId="me", id=email_id, format="full"
        ).execute()
        email = format_email(msg, include_body=True)

        text = (
            f"📧 **{email['subject']}**\n"
            f"From: {email['from']}\n"
            f"Date: {email['date']}\n"
            f"{'─'*40}\n"
            f"{email.get('body') or email['snippet']}"
        )
        return [types.TextContent(type="text", text=text)]

    # ── TRASH EMAIL ───────────────────────────────────────────
    elif name == "trash_email":
        email_id = arguments["email_id"]
        svc.users().messages().trash(userId="me", id=email_id).execute()
        return [types.TextContent(
            type="text",
            text=f"🗑️ Email `{email_id}` moved to Trash."
        )]

    # ── DELETE EMAIL ──────────────────────────────────────────
    elif name == "delete_email":
        email_id = arguments["email_id"]
        svc.users().messages().delete(userId="me", id=email_id).execute()
        return [types.TextContent(
            type="text",
            text=f"💥 Email `{email_id}` permanently deleted."
        )]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())