# 🖥️ Gmail Agent — Claude Desktop (MCP) Setup

This connects your Gmail agent directly into Claude Desktop so you can
chat with it naturally — no terminal, no localhost, no browser needed.

---

## 📁 Final Project Structure

```
gmail_agent/
├── gmail_mcp_server.py   ← MCP server (Claude Desktop talks to this)
├── gmail_agent.py        ← Original terminal agent (keep for reference)
├── requirements.txt
├── credentials.json      ← Your Google OAuth credentials
├── token.json            ← Auto-created after first login
└── .gitignore
```

---

## 🚀 Setup Steps

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

---

### Step 2 — Authenticate Gmail (one-time)
Run the original agent once to create token.json if you haven't already:
```bash
python gmail_agent.py
```
Log in via browser → then close it. You now have `token.json`.

---

### Step 3 — Find your Python path
In VS Code terminal run:
```bash
# Mac/Linux
which python3

# Windows
where python
```
Copy the full path — you'll need it in the next step.
Example: `C:\Users\YourName\AppData\Local\Programs\Python\Python311\python.exe`

---

### Step 4 — Edit Claude Desktop config file

Open this file in VS Code or any text editor:

**Mac:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

Add this (replace the paths with your actual paths):

```json
{
  "mcpServers": {
    "gmail-agent": {
      "command": "C:/Users/YourName/AppData/Local/Programs/Python/Python311/python.exe",
      "args": [
        "C:/Users/YourName/projects/gmail_agent/gmail_mcp_server.py"
      ]
    }
  }
}
```

> ⚠️ Use forward slashes `/` even on Windows. Double-check both paths are correct.

---

### Step 5 — Restart Claude Desktop

Fully quit and reopen Claude Desktop.

You should see a 🔧 **hammer icon** in the chat input box — that means the MCP server is connected!

---

## 💬 How to Use It

Just chat naturally with Claude Desktop:

| You say | Claude does |
|--------|-------------|
| "Show my inbox" | Lists recent emails |
| "Show last 5 emails" | Lists 5 emails |
| "Search for emails from john@example.com" | Searches Gmail |
| "Find unread emails" | Searches `is:unread` |
| "Read email 2" | Shows full body |
| "Trash email 3" | Moves to trash |
| "Permanently delete email 1" | Deletes forever ⚠️ |

---

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| No 🔧 hammer icon | Check paths in config are correct, restart Claude Desktop |
| `ModuleNotFoundError: mcp` | Run `pip install mcp` |
| `credentials.json not found` | Make sure it's in same folder as `gmail_mcp_server.py` |
| `token.json not found` | Run `python gmail_agent.py` once to authenticate |
| Config file not found | Create the file manually if it doesn't exist |

---

## 🔒 Security Reminder

Never commit `credentials.json` or `token.json` to Git.
Both are listed in `.gitignore` already.