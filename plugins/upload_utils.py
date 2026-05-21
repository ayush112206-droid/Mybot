"""
Upload utilities for TXT uploader.
Provides download (yt-dlp, aiohttp) and Telegram upload helpers.
Includes XOR decryption for Appx encrypted videos/PDFs.
Adapted from Txt-uploader-drm2-main/saini.py and VJ-Txt-Leech-Bot-main/core.py
"""

import os
import mmap
import time
import math
import random
import logging
import asyncio
import aiohttp
import aiofiles
import requests
import subprocess
import concurrent.futures

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from datetime import timedelta

logger = logging.getLogger(__name__)

# ─── Timer for throttling progress updates ───────────────────────────
class Timer:
    def __init__(self, time_between=5):
        self.start_time = time.time()
        self.time_between = time_between

    def can_send(self):
        if time.time() > (self.start_time + self.time_between):
            self.start_time = time.time()
            return True
        return False

timer = Timer()

# ─── Human-readable helpers ──────────────────────────────────────────
def hrb(value, digits=2):
    """Return human-readable file size."""
    if value is None:
        return "0B"
    chosen_unit = "B"
    for unit in ("KB", "MB", "GB", "TB"):
        if value > 1000:
            value /= 1024
            chosen_unit = unit
        else:
            break
    return f"{value:.{digits}f}{chosen_unit}"

def hrt(seconds, precision=1):
    """Return human-readable time delta."""
    pieces = []
    value = timedelta(seconds=seconds)
    if value.days:
        pieces.append(f"{value.days}d")
    secs = value.seconds
    if secs >= 3600:
        hours = int(secs / 3600)
        pieces.append(f"{hours}h")
        secs -= hours * 3600
    if secs >= 60:
        minutes = int(secs / 60)
        pieces.append(f"{minutes}m")
        secs -= minutes * 60
    if secs > 0 or not pieces:
        pieces.append(f"{secs}s")
    return "".join(pieces[:precision]) if precision else "".join(pieces)


# ─── Progress bar callback ───────────────────────────────────────────
async def progress_bar(current, total, reply, start):
    """Pyrogram upload progress callback — updates message with progress info."""
    if timer.can_send():
        now = time.time()
        diff = now - start
        if diff < 1:
            return
        perc = f"{current * 100 / total:.1f}%"
        speed = current / diff
        remaining = total - current
        eta = hrt(remaining / speed) if speed > 0 else "-"
        sp = hrb(speed) + "/s"
        tot = hrb(total)
        cur = hrb(current)

        bar_len = 10
        done = int(current * bar_len / total)
        bar = "🟩" * done + "⬜" * (bar_len - done)

        try:
            await reply.edit(
                f"<blockquote><code>"
                f"╭──⌯═══ 𝐔𝐩𝐥𝐨𝐚𝐝𝐢𝐧𝐠 ═══⌯──╮\n"
                f"├⚡ {bar}\n"
                f"├⚙️ Progress ➤ {perc}\n"
                f"├🚀 Speed    ➤ {sp}\n"
                f"├📟 Done     ➤ {cur}\n"
                f"├🧲 Size     ➤ {tot}\n"
                f"├🕑 ETA      ➤ {eta}\n"
                f"╰──═══════════════──╯"
                f"</code></blockquote>"
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            pass


# ─── Video duration via ffprobe ───────────────────────────────────────
def get_duration(filename):
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", filename],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        return int(float(result.stdout))
    except Exception:
        return 0


# ─── Download video via yt-dlp ────────────────────────────────────────
async def download_video(url, cmd, name):
    """
    Download a video using yt-dlp with aria2c accelerator.
    Returns the path of the downloaded file, or None on failure.
    """
    download_cmd = f'{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'
    logger.info(f"Download cmd: {download_cmd}")
    proc = subprocess.run(download_cmd, shell=True)

    # Try to find the output file (yt-dlp may change the extension)
    for candidate in [
        name,
        f"{name}.mp4",
        f"{name}.mkv",
        f"{name}.webm",
        f"{name}.mp4.webm",
    ]:
        if os.path.isfile(candidate):
            return candidate

    # Also try without any extra extension (strip .mp4 if already in name)
    base = name.rsplit(".", 1)[0] if "." in name else name
    for ext in [".mkv", ".mp4", ".webm", ".mp4.webm"]:
        if os.path.isfile(base + ext):
            return base + ext

    logger.warning(f"Downloaded file not found for: {name}")
    return None


# ─── Download file via aiohttp (PDF, images, etc.) ───────────────────
async def download_file(url, filepath):
    """
    Download a file (PDF, image, etc.) using aiohttp.
    Returns the filepath on success, None on failure.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(filepath, mode='wb')
                    await f.write(await resp.read())
                    await f.close()
                    return filepath
                else:
                    logger.warning(f"Download failed: HTTP {resp.status} for {url}")
                    return None
    except Exception as e:
        logger.error(f"Download error for {url}: {e}")
        return None


# ─── Upload video to Telegram ─────────────────────────────────────────
async def send_vid(bot: Client, m: Message, caption_text, filename, thumb, name, channel_id):
    """
    Generate thumbnail, upload video to Telegram channel with progress bar.
    Falls back to send_document if send_video fails.
    Cleans up files after upload.
    """
    thumb_path = f"{filename}.jpg"

    # Generate thumbnail at 10-second mark
    subprocess.run(
        f'ffmpeg -i "{filename}" -ss 00:00:10 -vframes 1 "{thumb_path}"',
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    reply = await bot.send_message(
        m.chat.id, f"**📤 Uploading:** `{name}`"
    )

    # Decide thumbnail
    if thumb and thumb != "/d" and os.path.isfile(thumb):
        thumbnail = thumb
    elif os.path.isfile(thumb_path):
        thumbnail = thumb_path
    else:
        thumbnail = None

    dur = get_duration(filename)
    start_time = time.time()

    try:
        await bot.send_video(
            chat_id=channel_id,
            video=filename,
            caption=caption_text,
            supports_streaming=True,
            height=720,
            width=1280,
            thumb=thumbnail,
            duration=dur,
            progress=progress_bar,
            progress_args=(reply, start_time)
        )
    except Exception as e:
        logger.warning(f"send_video failed, falling back to document: {e}")
        try:
            await bot.send_document(
                chat_id=channel_id,
                document=filename,
                caption=caption_text,
                progress=progress_bar,
                progress_args=(reply, start_time)
            )
        except Exception as e2:
            logger.error(f"send_document also failed: {e2}")

    # Cleanup
    try:
        await reply.delete(True)
    except Exception:
        pass
    if os.path.isfile(filename):
        os.remove(filename)
    if os.path.isfile(thumb_path):
        os.remove(thumb_path)


# ─── XOR Decryption for Appx encrypted files ─────────────────────────
def decrypt_file(file_path, key):
    """
    XOR-decrypt the first 28 bytes of a file using the given key.
    Appx uses this lightweight encryption on MKV/PDF files.
    The key is typically a numeric string (e.g. '6072676') extracted
    from the URL after the '*' separator.
    """
    if not os.path.exists(file_path):
        logger.warning(f"decrypt_file: file not found: {file_path}")
        return False

    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.warning(f"decrypt_file: empty file: {file_path}")
            return False

        num_bytes = min(28, file_size)
        with open(file_path, "r+b") as f:
            with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:
                for i in range(num_bytes):
                    mmapped_file[i] ^= ord(key[i]) if i < len(key) else i
        logger.info(f"Decrypted {file_path} (first {num_bytes} bytes)")
        return True
    except Exception as e:
        logger.error(f"decrypt_file error for {file_path}: {e}")
        return False


async def download_and_decrypt_video(url, cmd, name, key):
    """
    Download a video via yt-dlp, then XOR-decrypt the first 28 bytes.
    Returns the file path on success, None on failure.
    """
    video_path = await download_video(url, cmd, name)

    if video_path and os.path.isfile(video_path):
        decrypted = decrypt_file(video_path, key)
        if decrypted:
            logger.info(f"Video decrypted successfully: {video_path}")
            return video_path
        else:
            logger.warning(f"Failed to decrypt video: {video_path}")
            return video_path  # Still return — file exists, just maybe corrupt
    return None


async def download_and_decrypt_pdf(url, name, key):
    """
    Download an encrypted PDF (via aiohttp first, yt-dlp fallback),
    then XOR-decrypt the first 28 bytes.
    Returns the file path on success, None on failure.
    """
    filepath = f"{name}.pdf"

    # Try aiohttp first
    downloaded = await download_file(url, filepath)

    # Fallback to yt-dlp
    if not downloaded or not os.path.isfile(filepath):
        download_cmd = f'yt-dlp -o "{filepath}" "{url}" -R 25 --fragment-retries 25'
        try:
            subprocess.run(download_cmd, shell=True, check=True)
            logger.info(f"Downloaded PDF via yt-dlp: {filepath}")
        except subprocess.CalledProcessError as e:
            logger.error(f"PDF download failed: {e}")
            return None

    if not os.path.isfile(filepath):
        logger.warning(f"PDF file not found after download: {filepath}")
        return None

    # Decrypt
    decrypted = decrypt_file(filepath, key)
    if decrypted:
        logger.info(f"PDF decrypted successfully: {filepath}")
        return filepath
    else:
        logger.warning(f"PDF decryption failed: {filepath}")
        return filepath  # Return path anyway — file exists
