from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from config import load_config
from email_client import EmailClient

# ---------------------------------------------------------------------------
# Startup — load config and create shared client
# ---------------------------------------------------------------------------

_config = load_config()
_client = EmailClient(_config)

mcp = FastMCP("Email MCP Server")


# ---------------------------------------------------------------------------
# Tool: list_unread_emails
# ---------------------------------------------------------------------------


@mcp.tool()
def list_unread_emails(folder: str = "INBOX", limit: int = 10) -> list[dict[str, Any]]:
    """List unread emails from a mailbox folder, newest first.

    Args:
        folder: Mailbox folder to read from. Defaults to INBOX.
                Use list_folders to see all available folder names.
        limit: Maximum number of emails to return. Defaults to 10.

    Returns:
        List of email summaries, each with: id, subject, from, date, snippet.
        Use the returned id with get_email_by_id to fetch the full message.
    """
    return _client.list_unread(folder=folder, limit=limit)


# ---------------------------------------------------------------------------
# Tool: get_email_by_id
# ---------------------------------------------------------------------------


@mcp.tool()
def get_email_by_id(email_id: str, folder: str = "INBOX") -> dict[str, Any]:
    """Get the full details of an email by its UID.

    Args:
        email_id: The email UID as returned by list_unread_emails.
        folder: Mailbox folder where the email resides. Defaults to INBOX.

    Returns:
        Full email dict with: id, message_id, subject, from, to, cc, date,
        references, body_text, body_html, and attachments (list of metadata).
        Attachment metadata includes: filename, content_type, size_bytes.
        Use download_attachment to retrieve the actual attachment content.
    """
    return _client.get_email(email_id=email_id, folder=folder)


# ---------------------------------------------------------------------------
# Tool: reply_to_email
# ---------------------------------------------------------------------------


@mcp.tool()
def reply_to_email(
    email_id: str,
    body: str,
    folder: str = "INBOX",
) -> str:
    """Reply to an existing email.

    Automatically sets the correct In-Reply-To and References headers so the
    reply is threaded correctly in the recipient's mail client.

    Args:
        email_id: The email UID to reply to (from list_unread_emails).
        body: Plain text body of the reply message.
        folder: Folder where the original email resides. Defaults to INBOX.

    Returns:
        Confirmation string indicating the reply was sent.
    """
    original = _client.get_email(email_id=email_id, folder=folder)

    reply_headers: dict[str, str] = {}
    orig_message_id = original.get("message_id", "")
    if orig_message_id:
        reply_headers["In-Reply-To"] = orig_message_id
        existing_refs = original.get("references", "").strip()
        reply_headers["References"] = (
            f"{existing_refs} {orig_message_id}".strip()
        )

    _client.send_email(
        to=original["from"],
        subject=f"Re: {original['subject']}",
        body=body,
        reply_headers=reply_headers,
    )
    return f"Reply sent to {original['from']}."


# ---------------------------------------------------------------------------
# Tool: send_new_email
# ---------------------------------------------------------------------------


@mcp.tool()
def send_new_email(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    attachments: list[dict[str, str]] | None = None,
) -> str:
    """Send a new email to one or more recipients.

    Args:
        to: Recipient email address, or comma-separated list of addresses.
        subject: Subject line of the email.
        body: Plain text body of the email.
        cc: CC recipients as a comma-separated string. Optional.
        bcc: BCC recipients as a comma-separated string. Optional.
        attachments: List of file attachments. Each item must be a dict with:
                       - filename (str): name of the file, e.g. "report.pdf"
                       - content_base64 (str): base64-encoded file content
                       - content_type (str): MIME type, e.g. "application/pdf"
                     Optional — omit or pass null to send without attachments.

    Returns:
        Confirmation string indicating the email was sent.
    """
    _client.send_email(
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        attachments=attachments,
    )
    return f"Email sent to {to}."


# ---------------------------------------------------------------------------
# Tool: list_folders
# ---------------------------------------------------------------------------


@mcp.tool()
def list_folders() -> list[str]:
    """List all available mailbox folders on the email account.

    Returns:
        List of folder name strings (e.g. ["INBOX", "Sent", "Drafts", "Trash"]).
        These names can be used in the folder parameter of other tools.
    """
    return _client.list_folders()


# ---------------------------------------------------------------------------
# Tool: move_email_to_folder
# ---------------------------------------------------------------------------


@mcp.tool()
def move_email_to_folder(
    email_id: str,
    dest_folder: str,
    source_folder: str = "INBOX",
) -> str:
    """Move an email from one folder to another.

    Uses the standard IMAP COPY → mark Deleted → EXPUNGE pattern, which
    works correctly across all supported providers.

    Args:
        email_id: The email UID to move (from list_unread_emails).
        dest_folder: Destination folder name (use list_folders for valid names).
        source_folder: Source folder name. Defaults to INBOX.

    Returns:
        Confirmation string indicating the move was successful.
    """
    _client.move_email(
        email_id=email_id,
        source_folder=source_folder,
        dest_folder=dest_folder,
    )
    return f"Email {email_id} moved from '{source_folder}' to '{dest_folder}'."


# ---------------------------------------------------------------------------
# Tool: download_attachment
# ---------------------------------------------------------------------------


@mcp.tool()
def download_attachment(
    email_id: str,
    filename: str,
    folder: str = "INBOX",
) -> dict[str, str] | None:
    """Download a specific attachment from an email as base64-encoded content.

    Use get_email_by_id first to see available attachment filenames and their
    content_type values.

    Args:
        email_id: The email UID containing the attachment.
        filename: Exact filename of the attachment (e.g. "invoice.pdf").
        folder: Mailbox folder where the email resides. Defaults to INBOX.

    Returns:
        Dict with filename, content_type, and content_base64 (base64 string),
        or null if no attachment with that filename was found.
    """
    return _client.download_attachment(
        email_id=email_id,
        filename=filename,
        folder=folder,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
