"""
TXT Upload Plugin — Upload extracted content (videos/PDFs) to Telegram.
Usage: /upload  →  send TXT file  →  configure options  →  download & upload

Adapted from Txt-uploader-drm2-main/main.py and VJ-Txt-Leech-Bot-main/main.py.
"""

import os
import re
import asyncio
import logging
import time

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from config import Config
from plugins.upload_utils import (
    download_video, download_file, send_vid, progress_bar, get_duration,
    download_and_decrypt_video, download_and_decrypt_pdf, decrypt_file
)

logger = logging.getLogger(__name__)

# ─── Global state for cancel support ─────────────────────────────────
upload_processing = False
upload_cancel_requested = False


@Client.on_message(filters.command("stop_upload") & filters.private)
async def stop_upload_handler(bot: Client, m: Message):
    """Cancel an active upload task."""
    global upload_processing, upload_cancel_requested
    if upload_processing:
        upload_cancel_requested = True
        await m.reply_text("**🚦 Upload cancel requested. Stopping after current file...**")
    else:
        await m.reply_text("**⚡ No active upload process to cancel.**")


@Client.on_message(filters.command("upload") & filters.private)
async def upload_handler(bot: Client, m: Message):
    """
    Main upload command handler.
    Flow: receive TXT → parse links → ask options → download & upload each.
    """
    global upload_processing, upload_cancel_requested

    # ── Auth check ────────────────────────────────────────────────
    admin_ids = Config.ADMIN_ID if hasattr(Config, 'ADMIN_ID') else []
    if m.chat.id not in admin_ids:
        await m.reply_text(
            f"<blockquote><b>⚠️ You are not authorized to use this command.</b>\n"
            f"Your User ID: <code>{m.chat.id}</code></blockquote>"
        )
        return

    if upload_processing:
        await m.reply_text("**⚠️ An upload is already in progress. Use /stop_upload to cancel it first.**")
        return

    upload_processing = True
    upload_cancel_requested = False

    try:
        await _run_upload_flow(bot, m)
    except Exception as e:
        logger.error(f"Upload flow error: {e}", exc_info=True)
        await m.reply_text(f"**❌ Upload failed:**\n<blockquote>{e}</blockquote>")
    finally:
        upload_processing = False
        upload_cancel_requested = False


async def _run_upload_flow(bot: Client, m: Message):
    """Core upload flow — separated for clean error handling."""
    global upload_cancel_requested

    # ── Step 1: Receive TXT file ──────────────────────────────────
    editable = await m.reply_text(
        "**📄 Send me the .txt file containing links**\n"
        "<blockquote><i>Format: Title: URL (one per line)\n"
        "All prompts auto-timeout in 20 seconds with defaults.</i></blockquote>"
    )

    try:
        input_msg: Message = await bot.listen(m.chat.id, timeout=120)
    except asyncio.TimeoutError:
        await editable.edit("**⏰ Timed out waiting for file. Please try /upload again.**")
        return

    if not input_msg.document or not input_msg.document.file_name.endswith(".txt"):
        await m.reply_text("**❌ Please send a valid .txt file.**")
        await input_msg.delete(True)
        return

    x = await input_msg.download()
    await input_msg.delete(True)
    file_name = os.path.splitext(os.path.basename(x))[0]

    # ── Step 2: Parse the TXT file ────────────────────────────────
    pdf_count = vid_count = img_count = other_count = 0
    try:
        with open(x, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        lines = content.strip().split("\n")
        links = []
        for line in lines:
            line = line.strip()
            if "://" in line:
                parts = line.split("://", 1)
                links.append(parts)
                url_part = parts[1].lower() if len(parts) > 1 else ""
                if ".pdf" in url_part:
                    pdf_count += 1
                elif any(ext in url_part for ext in [".jpg", ".jpeg", ".png"]):
                    img_count += 1
                elif any(ext in url_part for ext in [".mkv", ".mp4", ".m3u8", ".mpd", ".webm"]):
                    vid_count += 1
                else:
                    # Assume video if no recognizable extension
                    vid_count += 1
        os.remove(x)
    except Exception as e:
        await m.reply_text(f"**❌ Failed to parse file:** {e}")
        if os.path.exists(x):
            os.remove(x)
        return

    if not links:
        await m.reply_text("**❌ No valid links found in the file.**")
        return

    # ── Step 3: Show stats and ask start index ────────────────────
    await editable.edit(
        f"**Total 🔗 links found: {len(links)}**\n"
        f"<blockquote>• 🎥 Videos: {vid_count}\n"
        f"• 📕 PDFs: {pdf_count}\n"
        f"• 🖼️ Images: {img_count}\n"
        f"• 📦 Other: {other_count}</blockquote>\n"
        f"**Send start index (or auto-starts from 1 in 20s)**"
    )
    try:
        input0: Message = await bot.listen(m.chat.id, timeout=20)
        raw_text = input0.text.strip()
        await input0.delete(True)
    except asyncio.TimeoutError:
        raw_text = "1"

    try:
        start_idx = max(1, int(raw_text))
    except ValueError:
        start_idx = 1

    if start_idx > len(links):
        await editable.edit(f"**❌ Start index must be between 1 and {len(links)}**")
        return

    # ── Step 4: Default or custom settings ────────────────────────
    await editable.edit("**Send /d for all defaults, or /no to customize each setting**")
    try:
        input_all: Message = await bot.listen(m.chat.id, timeout=20)
        choice = input_all.text.strip()
        await input_all.delete(True)
    except asyncio.TimeoutError:
        choice = "/d"

    if choice == "/d":
        b_name = file_name.replace("_", " ")
        quality = "480"
        credit = "Master Extractor"
        thumb = "/d"
        channel_id = m.chat.id
    else:
        # ── Batch name ──
        await editable.edit("**Enter Batch Name or /d for filename**")
        try:
            inp: Message = await bot.listen(m.chat.id, timeout=20)
            b_name = inp.text.strip() if inp.text.strip() != "/d" else file_name.replace("_", " ")
            await inp.delete(True)
        except asyncio.TimeoutError:
            b_name = file_name.replace("_", " ")

        # ── Quality ──
        await editable.edit("**Enter resolution: 144, 240, 360, 480, 720, 1080 (default: 480)**")
        try:
            inp: Message = await bot.listen(m.chat.id, timeout=20)
            quality = inp.text.strip() if inp.text.strip() != "/d" else "480"
            await inp.delete(True)
        except asyncio.TimeoutError:
            quality = "480"

        # ── Credit ──
        await editable.edit("**Enter credit name or /d for default**")
        try:
            inp: Message = await bot.listen(m.chat.id, timeout=20)
            credit = inp.text.strip() if inp.text.strip() != "/d" else "Master Extractor"
            await inp.delete(True)
        except asyncio.TimeoutError:
            credit = "Master Extractor"

        # ── Thumbnail ──
        await editable.edit("**Send thumbnail URL or /d for auto-generated**")
        try:
            inp: Message = await bot.listen(m.chat.id, timeout=20)
            thumb = inp.text.strip()
            await inp.delete(True)
        except asyncio.TimeoutError:
            thumb = "/d"

        if thumb.startswith("http://") or thumb.startswith("https://"):
            os.system(f"wget '{thumb}' -O 'upload_thumb.jpg' 2>/dev/null")
            thumb = "upload_thumb.jpg" if os.path.isfile("upload_thumb.jpg") else "/d"

        # ── Channel ID ──
        await editable.edit(
            "**Send Channel ID or /d to upload here**\n"
            "<blockquote><i>Make me admin in the channel.\n"
            "Use /id in your channel to get the ID.\n"
            "Example: -100XXXXXXXXXXX</i></blockquote>"
        )
        try:
            inp: Message = await bot.listen(m.chat.id, timeout=20)
            ch_text = inp.text.strip()
            await inp.delete(True)
        except asyncio.TimeoutError:
            ch_text = "/d"

        if ch_text == "/d":
            channel_id = m.chat.id
        else:
            try:
                channel_id = int(ch_text)
            except ValueError:
                channel_id = m.chat.id

    await editable.delete()

    # ── Step 5: Pin batch name ────────────────────────────────────
    if start_idx == 1:
        try:
            batch_msg = await bot.send_message(
                chat_id=channel_id,
                text=f"<blockquote><b>🎯 Batch: {b_name}</b></blockquote>"
            )
            if channel_id != m.chat.id:
                await bot.pin_chat_message(channel_id, batch_msg.id)
                # Delete the "pinned" service message
                try:
                    await bot.delete_messages(channel_id, batch_msg.id + 1)
                except Exception:
                    pass
                await m.reply_text(
                    f"<blockquote><b>🎯 Batch: {b_name}</b></blockquote>\n\n"
                    f"🔄 Upload started! Check your channel. I'll notify you when done 📩"
                )
        except Exception as e:
            logger.warning(f"Failed to pin batch: {e}")

    # ── Step 6: Download & Upload Loop ────────────────────────────
    count = start_idx
    failed_count = 0
    success_count = 0

    for i in range(start_idx - 1, len(links)):
        if upload_cancel_requested:
            await m.reply_text("🚦 **Upload stopped!**")
            return

        # Parse title and URL
        raw_title = links[i][0].strip()
        url_part = links[i][1].strip() if len(links[i]) > 1 else ""
        url = "https://" + url_part

        # Clean the title for filename use
        name1 = re.sub(r'[\\/:*?"<>|@#+\t]', '', raw_title).strip()
        name = f"{str(count).zfill(3)}) {name1[:60]}"
        namef = name1[:60]

        # ── Detect Appx encrypted URLs and extract key ──
        appx_key = None
        is_encrypted_video = False
        is_encrypted_pdf = False

        if 'encrypted.m' in url and '*' in url:
            # Encrypted Appx video: URL*KEY format
            appx_key = url.split('*')[1]
            url = url.split('*')[0]
            is_encrypted_video = True
            logger.info(f"Encrypted video detected, key={appx_key}")
        elif '.pdf*' in url:
            # Encrypted Appx PDF: URL*KEY format
            appx_key = url.split('*')[1]
            url = url.split('*')[0]
            is_encrypted_pdf = True
            logger.info(f"Encrypted PDF detected, key={appx_key}")
        elif 'encrypted' in url.lower() and '.pdf' in url.lower():
            # Encrypted PDF without key in URL (key may be missing)
            is_encrypted_pdf = True
            logger.info(f"Encrypted PDF detected (no embedded key)")

        # Determine URL transformations
        url = url.replace("file/d/", "uc?export=download&id=")
        url = url.replace("www.youtube-nocookie.com/embed", "youtu.be")
        url = url.replace("?modestbranding=1", "")
        url = url.replace("/view?usp=sharing", "")

        # Progress info
        remaining = len(links) - count
        progress_pct = (count / len(links)) * 100

        try:
            # ── PDF Upload ──
            if ".pdf" in url.lower():
                cc1 = (
                    f"[📕] Pdf ID: {str(count).zfill(3)}\n"
                    f"**File:** `{namef}.pdf`\n"
                    f"<blockquote><b>Batch: {b_name}</b></blockquote>\n"
                    f"**By➤** {credit}"
                )
                prog = await m.reply_text(
                    f"<blockquote>📥 <b>Downloading PDF [{count}/{len(links)}]</b>\n"
                    f"`{namef}`</blockquote>"
                )

                # ── Encrypted PDF (Appx) ──
                if is_encrypted_pdf and appx_key:
                    filepath = await download_and_decrypt_pdf(url, namef, appx_key)
                elif is_encrypted_pdf and not appx_key:
                    # Encrypted PDF but no key — download as-is, try to decrypt with empty
                    filepath = await download_file(url, f"{namef}.pdf")
                    if filepath is None:
                        cmd = f'yt-dlp -o "{namef}.pdf" "{url}" -R 25 --fragment-retries 25'
                        os.system(cmd)
                        filepath = f"{namef}.pdf" if os.path.isfile(f"{namef}.pdf") else None
                else:
                    # ── Normal PDF ──
                    filepath = await download_file(url, f"{namef}.pdf")
                    if filepath is None:
                        cmd = f'yt-dlp -o "{namef}.pdf" "{url}" -R 25 --fragment-retries 25'
                        os.system(cmd)
                        filepath = f"{namef}.pdf" if os.path.isfile(f"{namef}.pdf") else None

                if filepath and os.path.isfile(filepath):
                    await prog.delete(True)
                    start_time = time.time()
                    reply = await bot.send_message(m.chat.id, f"**📤 Uploading PDF:** `{namef}`")
                    await bot.send_document(
                        chat_id=channel_id,
                        document=filepath,
                        caption=cc1,
                        progress=progress_bar,
                        progress_args=(reply, start_time)
                    )
                    await reply.delete(True)
                    os.remove(filepath)
                    success_count += 1
                else:
                    await prog.delete(True)
                    await m.reply_text(
                        f"⚠️ **PDF download failed**\n"
                        f"**Name:** `{namef}`\n**URL:** `{url}`",
                        disable_web_page_preview=True
                    )
                    failed_count += 1

            # ── Image Upload ──
            elif any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png"]):
                ext = url.split(".")[-1].split("?")[0]
                cc_img = (
                    f"[🖼️] Img ID: {str(count).zfill(3)}\n"
                    f"**File:** `{namef}.{ext}`\n"
                    f"<blockquote><b>Batch: {b_name}</b></blockquote>\n"
                    f"**By➤** {credit}"
                )
                filepath = await download_file(url, f"{namef}.{ext}")
                if filepath and os.path.isfile(filepath):
                    await bot.send_photo(
                        chat_id=channel_id,
                        photo=filepath,
                        caption=cc_img
                    )
                    os.remove(filepath)
                    success_count += 1
                else:
                    await m.reply_text(
                        f"⚠️ **Image download failed**\n"
                        f"**Name:** `{namef}`\n**URL:** `{url}`",
                        disable_web_page_preview=True
                    )
                    failed_count += 1

            # ── Video Upload ──
            else:
                cc = (
                    f"[🎥] Vid ID: {str(count).zfill(3)}\n"
                    f"**Video:** `{namef} [{quality}p].mkv`\n"
                    f"<blockquote><b>Batch: {b_name}</b></blockquote>\n"
                    f"**By➤** {credit}"
                )

                # Build yt-dlp format string
                if "youtu" in url:
                    ytf = f'bv*[height<={quality}][ext=mp4]+ba[ext=m4a]/b[height<=?{quality}]'
                else:
                    ytf = f'b[height<={quality}]/bv[height<={quality}]+ba/b/bv+ba'

                cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'

                Show = (
                    f"<blockquote>🚀 <b>Progress: {progress_pct:.1f}%</b></blockquote>\n"
                    f"┣ 🔗 Index: {count}/{len(links)}  |  🖇️ Remain: {remaining}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"<blockquote><b>⬇️ Downloading {'🔐 Encrypted ' if is_encrypted_video else ''}Video...</b>\n"
                    f"`{namef}`</blockquote>"
                )
                prog = await m.reply_text(Show)

                # ── Encrypted Appx video ──
                if is_encrypted_video and appx_key:
                    res_file = await download_and_decrypt_video(url, cmd, name, appx_key)
                else:
                    # ── Normal video ──
                    res_file = await download_video(url, cmd, name)

                if res_file and os.path.isfile(res_file):
                    await send_vid(bot, m, cc, res_file, thumb, name, channel_id)
                    success_count += 1
                else:
                    await prog.delete(True)
                    await m.reply_text(
                        f"⚠️ **Video download failed**\n"
                        f"**Name:** `{namef}`\n**URL:** `{url}`",
                        disable_web_page_preview=True
                    )
                    failed_count += 1

                # Delete progress message if it still exists
                try:
                    await prog.delete(True)
                except Exception:
                    pass

        except FloodWait as e:
            logger.warning(f"FloodWait: sleeping {e.value}s")
            await asyncio.sleep(e.value)
            continue
        except Exception as e:
            logger.error(f"Error processing link {count}: {e}", exc_info=True)
            await m.reply_text(
                f"⚠️ **Error on link {count}**\n"
                f"**Name:** `{namef}`\n"
                f"<blockquote>{str(e)[:200]}</blockquote>"
            )
            failed_count += 1

        count += 1
        # Small delay to avoid rate limits
        await asyncio.sleep(1)

    # ── Step 7: Completion ────────────────────────────────────────
    await m.reply_text(
        f"<blockquote><b>✅ Upload Complete!</b></blockquote>\n\n"
        f"📊 **Results:**\n"
        f"• ✅ Success: {success_count}\n"
        f"• ❌ Failed: {failed_count}\n"
        f"• 📁 Total: {len(links)}\n\n"
        f"**Batch:** {b_name}"
    )
