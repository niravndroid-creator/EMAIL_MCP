from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, model_validator

# ---------------------------------------------------------------------------
# Provider presets — auto-fill IMAP/SMTP settings by provider name
# ---------------------------------------------------------------------------

PROVIDER_PRESETS: dict[str, dict] = {
    "gmail": {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "imap_use_ssl": True,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
    },
    "yahoo": {
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "imap_use_ssl": True,
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
    },
    "outlook": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "imap_use_ssl": True,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
    },
    "icloud": {
        "imap_host": "imap.mail.me.com",
        "imap_port": 993,
        "imap_use_ssl": True,
        "smtp_host": "smtp.mail.me.com",
        "smtp_port": 587,
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
    },
    "zoho": {
        "imap_host": "imap.zoho.com",
        "imap_port": 993,
        "imap_use_ssl": True,
        "smtp_host": "smtp.zoho.com",
        "smtp_port": 587,
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
    },
}


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------


class EmailConfig(BaseModel):
    email: str
    password: str
    imap_host: str
    imap_port: int = 993
    imap_use_ssl: bool = True
    smtp_host: str
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    @model_validator(mode="after")
    def validate_smtp_mode_exclusive(self) -> "EmailConfig":
        if self.smtp_use_tls and self.smtp_use_ssl:
            raise ValueError(
                "smtp_use_tls and smtp_use_ssl are mutually exclusive. "
                "Use smtp_use_tls=true with port 587, or smtp_use_ssl=true with port 465."
            )
        return self


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(path: str = "config.json") -> EmailConfig:
    """Load and validate configuration from a JSON file.

    Steps:
    1. Read config.json (raises FileNotFoundError with helpful message if missing).
    2. Strip all metadata keys (any key starting with '_').
    3. If 'provider' is set, apply the corresponding preset for imap/smtp fields.
       Explicit non-empty values in config.json always override preset defaults.
    4. Validate and return an EmailConfig instance.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file '{path}' not found. "
            "Copy 'config.example.json' to 'config.json' and fill in your credentials."
        )

    with config_path.open("r", encoding="utf-8") as f:
        raw: dict = json.load(f)

    # Remove documentation/metadata keys
    data = {k: v for k, v in raw.items() if not k.startswith("_")}

    # Apply provider preset
    provider = data.pop("provider", None)
    if provider:
        provider = str(provider).lower()
        if provider not in PROVIDER_PRESETS:
            raise ValueError(
                f"Unknown provider '{provider}'. "
                f"Valid options: {', '.join(PROVIDER_PRESETS)}"
            )
        preset = PROVIDER_PRESETS[provider].copy()
        # Preset fills only fields that are absent or left empty in config.json
        for key, value in preset.items():
            if not data.get(key):
                data[key] = value

    return EmailConfig(**data)
