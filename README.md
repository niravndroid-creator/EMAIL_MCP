# Email MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that exposes your email account as a set of AI-callable tools. Read, send, reply, move, and manage email directly from any MCP-compatible AI client (Claude Desktop, Cursor, VS Code Copilot, etc.) using IMAP and SMTP.

---

## Features

| Tool | Description |
|------|-------------|
| `list_unread_emails` | List unread emails from a folder (newest first) |
| `get_email_by_id` | Fetch full email details by UID |
| `send_new_email` | Send a new email with optional CC, BCC, and attachments |
| `reply_to_email` | Reply to an email with correct threading headers |
| `list_folders` | List all available mailbox folders |
| `move_email_to_folder` | Move an email between folders |
| `download_attachment` | Download an attachment as base64-encoded content |

---

## Supported Providers

Built-in presets auto-configure IMAP/SMTP settings:

| Provider | Preset name |
|----------|-------------|
| Gmail | `gmail` |
| Yahoo Mail | `yahoo` |
| Outlook / Microsoft 365 | `outlook` |
| iCloud Mail | `icloud` |
| Zoho Mail | `zoho` |
| Any custom server | _(set `provider: null` and fill fields manually)_ |

---

## Requirements

- Python ≥ 3.11
- [`uv`](https://docs.astral.sh/uv/) (recommended) **or** `pip`

---

## Installation

```bash
# Clone the repo
git clone https://github.com/niravndroid-creator/EMAIL_MCP.git
cd EMAIL_MCP

# Install dependencies
pip install -e .
# or with uv:
uv pip install -e .
```

---

## Configuration

Copy `config.json` and fill in your credentials:

```json
{
  "provider": "gmail",
  "email": "you@gmail.com",
  "password": "your_app_password_here"
}
```

> **App Passwords** — If your account has 2-factor authentication enabled (Gmail, Yahoo, iCloud), you must generate an App Password:
> - **Gmail**: <https://myaccount.google.com/apppasswords>
> - **Yahoo**: <https://login.yahoo.com/account/security>
> - **iCloud**: <https://appleid.apple.com>

For a **custom / self-hosted** mail server, set `provider` to `null` and specify all fields manually:

```json
{
  "provider": null,
  "email": "you@example.com",
  "password": "secret",
  "imap_host": "imap.example.com",
  "imap_port": 993,
  "imap_use_ssl": true,
  "smtp_host": "smtp.example.com",
  "smtp_port": 587,
  "smtp_use_tls": true,
  "smtp_use_ssl": false
}
```

> `config.json` is listed in `.gitignore` and will **never** be committed.

---

## Running the Server

```bash
# Directly
python server.py

# Via installed script
email-mcp

# Via MCP CLI (stdio transport)
mcp run server.py
```

---

## Integrating with AI Clients

### Claude Desktop

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "email": {
      "command": "python",
      "args": ["/absolute/path/to/EMAIL_MCP/server.py"]
    }
  }
}
```

### VS Code (GitHub Copilot / MCP extension)

```json
{
  "mcp": {
    "servers": {
      "email": {
        "type": "stdio",
        "command": "python",
        "args": ["/absolute/path/to/EMAIL_MCP/server.py"]
      }
    }
  }
}
```

---

## Project Structure

```
EMAIL_MCP/
├── server.py           # MCP tool definitions (FastMCP)
├── email_client.py     # IMAP / SMTP client logic
├── config.py           # Config model & provider presets
├── config.json         # Your local credentials (gitignored)
├── pyproject.toml      # Project metadata & dependencies
└── .gitignore
```

---

## Security Notes

- `config.json` is excluded from version control via `.gitignore`. **Never commit credentials.**
- Use App Passwords instead of your main account password wherever supported.
- The IMAP client opens and closes a connection per operation — no persistent sessions are held.

---

## License

MIT
