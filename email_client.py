from __future__ import annotations

import base64
import email
import email.header
import imaplib
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from config import EmailConfig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _decode_header_value(value: str) -> str:
    """Decode an RFC 2047-encoded email header value to a plain string."""
    parts = email.header.decode_header(value)
    decoded: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_bodies(msg: email.message.Message) -> tuple[str, str]:
    """Return (plain_text, html) bodies from a parsed email message."""
    plain = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = part.get("Content-Disposition", "")
            if "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if content_type == "text/plain" and not plain:
                plain = text
            elif content_type == "text/html" and not html:
                html = text
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html = text
            else:
                plain = text
    return plain, html


def _extract_attachment_meta(msg: email.message.Message) -> list[dict[str, Any]]:
    """Return metadata for every attachment in the message (no content bytes)."""
    attachments: list[dict[str, Any]] = []
    for part in msg.walk():
        disposition = part.get("Content-Disposition", "")
        if "attachment" not in disposition:
            continue
        filename = part.get_filename()
        if not filename:
            continue
        filename = _decode_header_value(filename)
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            {
                "filename": filename,
                "content_type": part.get_content_type(),
                "size_bytes": len(payload),
            }
        )
    return attachments


def _extract_attachment_content(
    msg: email.message.Message, filename: str
) -> dict[str, str] | None:
    """Return base64-encoded content for a named attachment, or None if not found."""
    for part in msg.walk():
        disposition = part.get("Content-Disposition", "")
        if "attachment" not in disposition:
            continue
        part_filename = part.get_filename()
        if not part_filename:
            continue
        if _decode_header_value(part_filename) == filename:
            payload = part.get_payload(decode=True) or b""
            return {
                "filename": filename,
                "content_type": part.get_content_type(),
                "content_base64": base64.b64encode(payload).decode("ascii"),
            }
    return None


# ---------------------------------------------------------------------------
# EmailClient
# ---------------------------------------------------------------------------


class EmailClient:
    """Stateless email client that opens and closes connections per operation."""

    def __init__(self, config: EmailConfig) -> None:
        self._cfg = config

    # ------------------------------------------------------------------
    # Private connection helpers
    # ------------------------------------------------------------------

    def _imap_connect(self) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        cfg = self._cfg
        if cfg.imap_use_ssl:
            conn: imaplib.IMAP4_SSL | imaplib.IMAP4 = imaplib.IMAP4_SSL(
                cfg.imap_host, cfg.imap_port
            )
        else:
            conn = imaplib.IMAP4(cfg.imap_host, cfg.imap_port)
        conn.login(cfg.email, cfg.password)
        return conn

    def _fetch_parsed_message(
        self,
        conn: imaplib.IMAP4_SSL | imaplib.IMAP4,
        uid: str,
    ) -> email.message.Message:
        _, data = conn.uid("fetch", uid, "(RFC822)")
        raw_bytes: bytes = data[0][1]  # type: ignore[index]
        return email.message_from_bytes(raw_bytes)

    # ------------------------------------------------------------------
    # IMAP — read operations
    # ------------------------------------------------------------------

    def list_folders(self) -> list[str]:
        """Return all mailbox folder names available on the account."""
        conn = self._imap_connect()
        try:
            _, folder_list = conn.list()
            folders: list[str] = []
            for item in folder_list:
                if not isinstance(item, bytes):
                    continue
                decoded = item.decode()
                # IMAP LIST response format: (\Flags) "delimiter" "Name"
                # Split on the delimiter character in quotes
                if '" "' in decoded:
                    name = decoded.split('" "', 1)[-1].strip().strip('"')
                elif "\" /" in decoded:
                    name = decoded.split("\" /", 1)[-1].strip().strip('"')
                else:
                    # Fallback: last whitespace-separated token
                    name = decoded.rsplit(None, 1)[-1].strip().strip('"')
                if name:
                    folders.append(name)
            return folders
        finally:
            conn.logout()

    def list_unread(
        self, folder: str = "INBOX", limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return summary dicts for unread emails in *folder*, newest first."""
        conn = self._imap_connect()
        try:
            conn.select(folder, readonly=True)
            _, uid_data = conn.uid("search", None, "UNSEEN")
            uids: list[bytes] = uid_data[0].split()
            # Newest-first: reverse the UID list, then cap at limit
            uids = uids[::-1][:limit]
            results: list[dict[str, Any]] = []
            for uid_bytes in uids:
                uid = uid_bytes.decode()
                msg = self._fetch_parsed_message(conn, uid)
                subject = _decode_header_value(msg.get("Subject", "(no subject)"))
                sender = _decode_header_value(msg.get("From", ""))
                date = msg.get("Date", "")
                plain, _ = _extract_bodies(msg)
                snippet = plain[:200].replace("\n", " ").strip()
                results.append(
                    {
                        "id": uid,
                        "subject": subject,
                        "from": sender,
                        "date": date,
                        "snippet": snippet,
                    }
                )
            return results
        finally:
            conn.logout()

    def get_email(
        self, email_id: str, folder: str = "INBOX"
    ) -> dict[str, Any]:
        """Return full email details including bodies and attachment metadata."""
        conn = self._imap_connect()
        try:
            conn.select(folder, readonly=True)
            msg = self._fetch_parsed_message(conn, email_id)
            plain, html = _extract_bodies(msg)
            attachments = _extract_attachment_meta(msg)
            return {
                "id": email_id,
                "message_id": msg.get("Message-ID", ""),
                "subject": _decode_header_value(msg.get("Subject", "(no subject)")),
                "from": _decode_header_value(msg.get("From", "")),
                "to": _decode_header_value(msg.get("To", "")),
                "cc": _decode_header_value(msg.get("Cc", "")),
                "date": msg.get("Date", ""),
                "references": msg.get("References", ""),
                "body_text": plain,
                "body_html": html,
                "attachments": attachments,
            }
        finally:
            conn.logout()

    def download_attachment(
        self, email_id: str, filename: str, folder: str = "INBOX"
    ) -> dict[str, str] | None:
        """Return base64-encoded bytes for a named attachment, or None if not found."""
        conn = self._imap_connect()
        try:
            conn.select(folder, readonly=True)
            msg = self._fetch_parsed_message(conn, email_id)
            return _extract_attachment_content(msg, filename)
        finally:
            conn.logout()

    def move_email(
        self, email_id: str, source_folder: str, dest_folder: str
    ) -> None:
        """Move an email using COPY → STORE \\Deleted → EXPUNGE."""
        conn = self._imap_connect()
        try:
            conn.select(source_folder)
            # Copy to destination folder
            result, _ = conn.uid("copy", email_id, dest_folder)
            if result != "OK":
                raise RuntimeError(
                    f"IMAP COPY failed for UID {email_id} → '{dest_folder}'"
                )
            # Mark original as deleted
            conn.uid("store", email_id, "+FLAGS", r"(\Deleted)")
            # Permanently remove deleted messages
            conn.expunge()
        finally:
            conn.logout()

    # ------------------------------------------------------------------
    # SMTP — send operations
    # ------------------------------------------------------------------

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        bcc: str | None = None,
        reply_headers: dict[str, str] | None = None,
        attachments: list[dict[str, str]] | None = None,
    ) -> None:
        """Build and send an email via SMTP.

        attachments: list of dicts with keys:
            - filename       (str)
            - content_base64 (str)  base64-encoded file bytes
            - content_type   (str)  e.g. "application/pdf"
        """
        cfg = self._cfg
        msg = MIMEMultipart()
        msg["From"] = cfg.email
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if reply_headers:
            for header, value in reply_headers.items():
                msg[header] = value

        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Attach files
        if attachments:
            for att in attachments:
                filename = att["filename"]
                content_type = att.get("content_type", "application/octet-stream")
                raw_bytes = base64.b64decode(att["content_base64"])
                maintype, subtype = (
                    content_type.split("/", 1)
                    if "/" in content_type
                    else ("application", "octet-stream")
                )
                part = MIMEBase(maintype, subtype)
                part.set_payload(raw_bytes)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(part)

        # Build full recipients list (To + Cc + Bcc)
        recipients: list[str] = [addr.strip() for addr in to.split(",") if addr.strip()]
        if cc:
            recipients += [addr.strip() for addr in cc.split(",") if addr.strip()]
        if bcc:
            recipients += [addr.strip() for addr in bcc.split(",") if addr.strip()]

        raw_message = msg.as_string()

        if cfg.smtp_use_ssl:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=ctx) as server:
                server.login(cfg.email, cfg.password)
                server.sendmail(cfg.email, recipients, raw_message)
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                if cfg.smtp_use_tls:
                    ctx = ssl.create_default_context()
                    server.starttls(context=ctx)
                server.login(cfg.email, cfg.password)
                server.sendmail(cfg.email, recipients, raw_message)
