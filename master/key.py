"""
master/key.py — Keyboard generators, photo helpers, and APPX pagination.
"""
import logging
import math
import random
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import Config

logger = logging.getLogger(__name__)

APPS_PER_PAGE = 6

# Maps safe callback_data → {app_name, api_url}
app_identifier_map: dict = {}


# ── DB helpers ────────────────────────────────────────────────────────────────

async def get_appx_api() -> list:
    """APPX API entries (DB removed — returns empty list)."""
    return []


# ── Keyboard generators ───────────────────────────────────────────────────────

async def gen_apps_free_kb(page: int = 0) -> InlineKeyboardMarkup:
    """
    Paginated APPX free-apps keyboard.
    Returns a single InlineKeyboardMarkup (not a tuple).
    """
    try:
        apis = await get_appx_api()

        if not apis:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ No Apps Available", callback_data="none")],
                [InlineKeyboardButton("🏠 Menu", callback_data="home")]
            ])

        sorted_apps = sorted(apis, key=lambda x: x.get("app_name", "").lower())

        global app_identifier_map
        app_identifier_map = {}
        for app in sorted_apps:
            name     = app.get("app_name", "")
            safe_id  = f"free_{name[:20].replace(' ', '_').lower()}"
            app_identifier_map[safe_id] = {
                "app_name": name,
                "api_url":  app.get("api_url", "")
            }

        total_apps  = len(sorted_apps)
        total_pages = max(1, math.ceil(total_apps / APPS_PER_PAGE))
        page        = max(0, min(page, total_pages - 1))

        start       = page * APPS_PER_PAGE
        end         = min(start + APPS_PER_PAGE, total_apps)
        page_apps   = sorted_apps[start:end]

        keyboard, row = [], []
        for app in page_apps:
            name    = app.get("app_name", "Unknown")
            safe_id = f"free_{name[:20].replace(' ', '_').lower()}"
            row.append(InlineKeyboardButton(f"📱 {name}", callback_data=safe_id))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"appx_page_{page - 1}"))
        nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="none"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"appx_page_{page + 1}"))

        keyboard.append(nav)
        keyboard.append([InlineKeyboardButton("🏠 Menu", callback_data="home")])

        return InlineKeyboardMarkup(keyboard)

    except Exception as e:
        logger.error(f"gen_apps_free_kb error: {e}")
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Error Loading Apps", callback_data="none")],
            [InlineKeyboardButton("🏠 Menu", callback_data="home")]
        ])


async def appx_page(call_msg, page: int):
    """
    Navigate APPX free-apps pages.
    Called as: await key.appx_page(call_msg, page)
    """
    try:
        markup = await gen_apps_free_kb(page=page)
        await call_msg.edit_reply_markup(reply_markup=markup)
    except Exception as e:
        logger.error(f"appx_page error: {e}")


def get_handle_appx_free_data(data: str):
    """Resolve callback_data → {app_name, api_url} or None."""
    info = app_identifier_map.get(data)
    if info:
        return info
    logger.warning(f"App '{data}' not found in map — send /app to reload.")
    return None


# ── Inline keyboard helpers ───────────────────────────────────────────────────

def join_user() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Our Channel", url=Config.CH_URL)],
        [InlineKeyboardButton("👤 Contact Admin",    url=Config.OWNER)]
    ])


def contact() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Contact Admin",    url=Config.OWNER)],
        [InlineKeyboardButton("📢 Join Our Channel", url=Config.CH_URL)]
    ])


# ── Photo helper ──────────────────────────────────────────────────────────────

async def send_random_photo() -> str:
    """Return a random photo URL (picsum) or configured THUMB_URL."""
    try:
        return f"https://picsum.photos/500/300?random={random.randint(1, 99999)}"
    except Exception:
        return Config.THUMB_URL or "https://picsum.photos/500/300"
