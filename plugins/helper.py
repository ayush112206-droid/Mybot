"""
plugins/helper.py — Admin commands (DB-free version)
"""
import logging
import subprocess
import pytz
from datetime import datetime
from pyrogram import filters, Client as bot
from config import Config

LOGGER = logging.getLogger(__name__)
IST    = pytz.timezone('Asia/Kolkata')

_thumb_result = subprocess.getstatusoutput(f"wget -q '{Config.THUMB_URL}' -O 'thumb.jpg'")
thumb = "thumb.jpg" if _thumb_result[0] == 0 else None


@bot.on_message(filters.command("status") & filters.private)
async def status_command(_, m):
    if m.chat.id not in Config.ADMIN_ID:
        return await m.reply_text("🚫 You are not authorized to use this command.")
    await m.reply_text(
        f"📊 **Bot Status**\n\n"
        f"🟢 Bot is running\n"
        f"🕐 Time (IST): **{datetime.now(IST).strftime('%d %b %Y, %I:%M %p')}**"
    )
