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

    Supports two config.json formats:

    1. Schema format — parameters defined under config.properties, with values
       stored in each property's 'default' field:
         {
           "config": {
             "properties": {
               "email":    { "default": "you@example.com" },
               "password": { "default": "app_password" },
               "provider": { "default": "gmail" },
               ...
             }
           }
         }

    2. Flat format — parameters as top-level keys (legacy):
         { "provider": "gmail", "email": "you@example.com", ... }

    In both formats:
    - If 'provider' is set, IMAP/SMTP fields are auto-filled from the preset.
    - Explicit non-empty values always override preset defaults.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file '{path}' not found. "
            "Fill in your credentials in 'config.json' and try again."
        )

    with config_path.open("r", encoding="utf-8") as f:
        raw: dict = json.load(f)

    # Detect schema format: { "config": { "properties": { ... } } }
    if "config" in raw and "properties" in raw["config"]:
        properties: dict = raw["config"]["properties"]
        data = {
            key: prop["default"]
            for key, prop in properties.items()
            if "default" in prop
        }
    else:
        # Flat format — strip metadata keys (any key starting with '_')
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
