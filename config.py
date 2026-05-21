"""
Configuration module — reads all settings from environment variables.
Set these as env vars on Heroku / Railway / Render, or in a .env file locally.
"""
import os


class Config:
    # ── Telegram ──────────────────────────────────────────────────────────────
    BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
    API_ID      = int(os.environ.get("API_ID", "0"))
    API_HASH    = os.environ.get("API_HASH", "")

    # ── Admin / Owner ─────────────────────────────────────────────────────────
    ADMIN_ID    = [int(x) for x in os.environ.get("ADMIN_ID", "0").split(",") if x.strip()]
    OWNER_ID    = int(os.environ.get("OWNER_ID", "0"))

    # ── Channel / Owner Links ─────────────────────────────────────────────────
    CHANNEL     = int(os.environ.get("CHANNEL", "0"))
    CH_URL      = os.environ.get("CH_URL", "https://t.me/your_channel")
    OWNER       = os.environ.get("OWNER", "https://t.me/your_username")

    # ── Media ─────────────────────────────────────────────────────────────────
    THUMB_URL   = os.environ.get("THUMB_URL", "https://picsum.photos/500/300")

    # ── Optional Channel IDs for extractors ──────────────────────────────────
    CHANNEL_ID  = os.environ.get("CHANNEL_ID", "")
    CHANNEL_ID2 = os.environ.get("CHANNEL_ID2", "")

    # ── Bot Display Info ──────────────────────────────────────────────────────
    BOT_TEXT     = os.environ.get("BOT_TEXT", "Master Extractor")
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "MasterExtractorBot")
    HOST         = os.environ.get("HOST", "https://api.masterapi.tech")
