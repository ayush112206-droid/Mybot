from pyrogram import Client as bot, filters
import os, sys, aiofiles, asyncio
from config import Config
import msg, io, master.key as key
from datetime import datetime, timedelta
import pytz, subprocess, shutil
from main import LOGGER
import requests, cloudscraper
from urllib.parse import unquote
scraper = cloudscraper.create_scraper()

thumb = "thumb.jpg" if subprocess.getstatusoutput(f"wget '{Config.THUMB_URL}' -O 'thumb.jpg'")[0] == 0 else None
IST = pytz.timezone('Asia/Kolkata')


async def clear_handler():
    extensions_to_clear = [".mp4", ".jpg", ".png", ".mkv", ".pdf", ".ts", ".m4a", ".mpd", ".m3u8", ".json", ".txt"]
    files_cleared = False
    directory = os.getcwd()
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(tuple(extensions_to_clear)):
                os.remove(os.path.join(root, file))
                files_cleared = True
    temp_dir = os.path.join(directory, "temp")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        files_cleared = True
    if files_cleared:
        LOGGER.info("✅ Files cleared successfully!")
    else:
        LOGGER.info("No files with specified extensions were found.")


@bot.on_message(filters.command("stop") & filters.private)
async def stop_handler(_, m):
    user_id = m.from_user.id
    if user_id not in Config.ADMIN_ID:
        await m.reply_text(msg.UPGRADE, reply_markup=key.contact())
        return
    await clear_handler()
    await m.reply_text("🚦**STOPPED**🚦", True)
    os.execl(sys.executable, sys.executable, *sys.argv)
