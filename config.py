"""
Configuration module — reads all settings from environment variables.
Set these as env vars on Heroku / Railway / Render, or in a .env file locally.
"""
import os


class Config:
    # ── Telegram ──────────────────────────────────────────────────────────────
    BOT_TOKEN   = os.environ.get("BOT_TOKEN", "8629684327:AAFzATaGfQhrf8hPyVH4wB78P9ZotSAVXn8")
    API_ID      = int(os.environ.get("API_ID", "21503125"))
    API_HASH    = os.environ.get("API_HASH", "bab9855c442e9e4e87f413cb5b9dc3f9")

    # ── Admin / Owner ─────────────────────────────────────────────────────────
    ADMIN_ID    = [int(x) for x in os.environ.get("ADMIN_ID", "8033638335").split(",") if x.strip()]
    OWNER_ID    = int(os.environ.get("OWNER_ID", "8033638335"))

    # ── Channel / Owner Links ─────────────────────────────────────────────────
    CHANNEL     = int(os.environ.get("CHANNEL", "0"))
    CH_URL      = os.environ.get("CH_URL", "https://t.me/your_channel")
    OWNER       = os.environ.get("OWNER", "https://t.me/your_username")

    # ── Media ─────────────────────────────────────────────────────────────────
    THUMB_URL   = os.environ.get("THUMB_URL", "https://picsum.photos/500/300")

    # ── Optional Channel IDs for extractors ──────────────────────────────────
    CHANNEL_ID  = os.environ.get("CHANNEL_ID", "-1003801252137")
    CHANNEL_ID2 = os.environ.get("CHANNEL_ID2", "-1003801252137")

    # ── Bot Display Info ──────────────────────────────────────────────────────
    BOT_TEXT     = os.environ.get("BOT_TEXT", "Master Extractor")
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "Dbrajdarkuniversebot")
    HOST         = os.environ.get("HOST", "https://api.masterapi.tech")
