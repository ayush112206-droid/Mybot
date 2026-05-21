"""
KD Campus / KD Live extractor module.
Adapted from ApnaEx-main/Extractor/modules/kdlive.py
"""
import json
import time
import httpx
import hashlib
from config import Config
from datetime import datetime
import pytz
import asyncio
import os
import logging
from pyrogram.enums import ParseMode
from pyrogram.types import Message
import requests
import zipfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEOUT = 120
API_KEY = "kdc123"
THUMB_PATH = "thumb.jpg"

india_timezone = pytz.timezone('Asia/Kolkata')


async def handle_kd_logic(app, message):
    """Main KD handler - called from __init__.py callback"""
    try:
        appname = 'KD Campus'
        await extract(app, message, appname)
    except Exception as e:
        logger.error(f"Error in kdlive: {e}")
        await message.reply_text(
            "❌ <b>An error occurred</b>\n\n"
            f"Error details: <code>{str(e)}</code>\n\n"
            "Please try again or contact support."
        )


async def download_thumbnail():
    """Download thumbnail image if not already downloaded"""
    THUMB_URL = getattr(Config, 'THUMB_URL', '')
    if not THUMB_URL:
        return None
    if not os.path.exists(THUMB_PATH):
        try:
            response = requests.get(THUMB_URL)
            if response.status_code == 200:
                with open(THUMB_PATH, 'wb') as f:
                    f.write(response.content)
                return THUMB_PATH
        except Exception as e:
            logger.error(f"Error downloading thumbnail: {e}")
            return None
    return THUMB_PATH


async def extract(app, m, appname):
    try:
        start_time = time.time()
        BOT_TEXT = getattr(Config, 'BOT_TEXT', 'Master Extractor')

        editable = await m.reply_text(
            "🔹 <b>KD CAMPUS EXTRACTOR PRO</b> 🔹\n\n"
            "Send login details in one of these formats:\n"
            "1️⃣ <b>ID*Password:</b> <code>ID*Password</code>\n"
            "2️⃣ <b>Token:</b> <code>your_token</code>\n\n"
            "<i>Example:</i>\n"
            "- ID*Pass: <code>6969696969*password123</code>\n"
            "- Token: <code>abcdef123456</code>",
            parse_mode=ParseMode.HTML
        )

        try:
            input1 = await app.listen(m.chat.id, timeout=TIMEOUT)
            id_password = input1.text
            await input1.delete()
        except asyncio.TimeoutError:
            await editable.edit_text("⚠️ <b>Timeout:</b> No response received.", parse_mode=ParseMode.HTML)
            return

        async with httpx.AsyncClient() as client:
            try:
                if '*' in id_password:
                    mob, pwd = id_password.split('*', 1)
                    password = hashlib.sha512(pwd.encode()).hexdigest()
                    payload = {
                        "code": "", "valid_id": "", "api_key": API_KEY,
                        "mobilenumber": mob, "password": password
                    }
                    headers = {
                        "User-Agent": "okhttp/4.10.0",
                        "Accept-Encoding": "gzip",
                        "Content-Type": "application/json; charset=UTF-8"
                    }
                    resp = (await client.post(
                        "https://web.kdcampus.live/android/Usersn/login_user",
                        json=payload, headers=headers
                    )).json()

                    if 'data' not in resp:
                        await editable.edit_text("❌ <b>Login Failed</b>", parse_mode=ParseMode.HTML)
                        return

                    user_data = resp['data']
                    token = user_data['connection_key']
                    userid = user_data['id']
                else:
                    token = id_password
                    try:
                        validate_resp = (await client.get(
                            f'https://web.kdcampus.live/android/Dashboard/get_mycourse_data_renew_new/{token}/0/4'
                        )).json()
                        if not validate_resp:
                            await editable.edit_text("❌ <b>Invalid Token</b>", parse_mode=ParseMode.HTML)
                            return
                        userid = "0"
                    except:
                        await editable.edit_text("❌ <b>Invalid Token</b>", parse_mode=ParseMode.HTML)
                        return

                # Fetch courses
                resp = (await client.get(
                    f'https://web.kdcampus.live/android/Dashboard/get_mycourse_data_renew_new/{token}/{userid}/4'
                )).json()

                if not resp:
                    await editable.edit_text("❌ No courses found.", parse_mode=ParseMode.HTML)
                    return

                batch_list = ""
                batch_ids = []
                batch_data = []

                for item in resp:
                    course_id = item['course_id']
                    batch_id = item['batch_id']
                    name = item['batch_name']
                    image = f"http://kdcampus.live/uploaded/landing_images/{item['banner_image_name']}"

                    batch_list += f"<code>{batch_id}_{course_id}</code> - <b>{name}</b> 💰\n\n"
                    batch_ids.append(f"{batch_id}_{course_id}")
                    batch_data.append({'id': str(course_id), 'batch_id': str(batch_id), 'name': name, 'image': image})

                await editable.edit_text(
                    f"✅ <b>{appname} Login Successful</b>\n\n"
                    f"📚 <b>Available Batches:</b>\n\n{batch_list}",
                    parse_mode=ParseMode.HTML
                )

                input2 = await app.ask(
                    m.chat.id,
                    f"<b>📥 Send the Batch ID to download</b>\n\n"
                    f"<b>💡 For ALL:</b> <code>{','.join(batch_ids)}</code>\n\n"
                    f"<i>Supports multiple IDs separated by comma</i>",
                    parse_mode=ParseMode.HTML
                )

                selected_ids = [id.strip() for id in input2.text.strip().split(',') if id.strip()]
                await input2.delete()
                await editable.delete()

                if not selected_ids:
                    await m.reply_text("❌ No valid batch IDs.", parse_mode=ParseMode.HTML)
                    return

                for bid_str in selected_ids:
                    if '_' not in bid_str:
                        await m.reply_text(f"❌ Invalid format: {bid_str}", parse_mode=ParseMode.HTML)
                        continue

                    progress_msg = await m.reply_text(
                        "🔄 <b>Processing</b>\n"
                        f"└─ Batch: <code>{bid_str}</code>",
                        parse_mode=ParseMode.HTML
                    )

                    try:
                        bid, ccid = bid_str.split('_')
                        batch_info = next((b for b in batch_data if b['batch_id'] == bid and b['id'] == ccid), None)

                        if not batch_info:
                            await progress_msg.edit_text(f"❌ Invalid batch ID: {bid_str}", parse_mode=ParseMode.HTML)
                            continue

                        all_urls = []
                        topic_wise_content = {}

                        try:
                            subjects_response = await client.get(
                                f"https://web.kdcampus.live/android/Dashboard/course_subject/{token}/{userid}/{ccid}/{bid}"
                            )
                            subjects_data = subjects_response.json()
                            if 'subjects' not in subjects_data or not subjects_data['subjects']:
                                await progress_msg.edit_text(f"❌ No subjects found for: {bid_str}", parse_mode=ParseMode.HTML)
                                continue
                            subjects = subjects_data['subjects']
                        except Exception as e:
                            await progress_msg.edit_text(f"❌ Error: <code>{str(e)}</code>", parse_mode=ParseMode.HTML)
                            continue

                        total_subjects = len(subjects)
                        processed = 0
                        total_videos = 0
                        total_pdfs = 0

                        for subject in subjects:
                            sid = subject['id']
                            subject_name = subject['subject_name']
                            subject_content = []

                            try:
                                await progress_msg.edit_text(
                                    f"🔄 <b>Processing</b>\n"
                                    f"├─ Progress: {processed}/{total_subjects}\n"
                                    f"├─ Videos: {total_videos}\n"
                                    f"├─ PDFs: {total_pdfs}\n"
                                    f"└─ Current: <code>{subject_name}</code>",
                                    parse_mode=ParseMode.HTML
                                )
                            except:
                                pass

                            try:
                                videos_response = await client.get(
                                    f"https://web.kdcampus.live/android/Dashboard/course_details_video/{token}/{userid}/{ccid}/{bid}/0/{sid}/0"
                                )
                                videos = videos_response.json()
                                if videos and isinstance(videos, list):
                                    for video in reversed(videos):
                                        title = video.get('content_title', '').strip()
                                        url = video.get('jwplayer_id', '')
                                        if title and url:
                                            url = "https://" + url
                                            all_urls.append(f"{title}: {url}")
                                            subject_content.append(f"🎬 {title}\n{url}")
                                            total_videos += 1
                            except Exception as e:
                                logger.error(f"Error fetching videos: {e}")

                            try:
                                pdfs_response = await client.get(
                                    f"https://web.kdcampus.live/android/Dashboard/course_details_pdf/{token}/{userid}/{ccid}/{bid}/0/{sid}/0"
                                )
                                pdfs = pdfs_response.json()
                                if pdfs and isinstance(pdfs, list):
                                    for pdf in reversed(pdfs):
                                        title = pdf.get('content_title', '').strip()
                                        filename = pdf.get('file_name', '')
                                        if title and filename:
                                            url = "https://kdcampus.live/uploaded/content_data/" + filename
                                            all_urls.append(f"{title}: {url}")
                                            subject_content.append(f"📄 {title}\n{url}")
                                            total_pdfs += 1
                            except Exception as e:
                                logger.error(f"Error fetching PDFs: {e}")

                            if subject_content:
                                topic_wise_content[subject_name] = subject_content
                            processed += 1

                        if not all_urls:
                            await progress_msg.edit_text(f"❌ No content found.", parse_mode=ParseMode.HTML)
                            continue

                        batch_name = batch_info['name']
                        timestamp = int(time.time())
                        txt_filename = f"KD_{batch_name}_{timestamp}.txt"

                        with open(txt_filename, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(all_urls))

                        duration = time.time() - start_time
                        minutes, seconds = divmod(duration, 60)

                        caption = (
                            f"🎓 <b>COURSE EXTRACTED</b> 🎓\n\n"
                            f"📱 <b>APP:</b> {appname}\n"
                            f"📚 <b>BATCH:</b> {batch_name}\n"
                            f"⏱ <b>TIME:</b> {int(minutes):02d}:{int(seconds):02d}\n"
                            f"📅 <b>DATE:</b> {datetime.now(india_timezone).strftime('%d-%m-%Y %H:%M:%S')} IST\n\n"
                            f"📊 <b>STATS</b>\n"
                            f"├─ 📁 Total: {len(all_urls)}\n"
                            f"├─ 🎬 Videos: {total_videos}\n"
                            f"├─ 📄 PDFs: {total_pdfs}\n"
                            f"└─ 📚 Topics: {len(topic_wise_content)}\n\n"
                            f"🚀 <b>By:</b> @{(await app.get_me()).username}\n\n"
                            f"<code>╾───• {BOT_TEXT} •───╼</code>"
                        )

                        try:
                            thumb_path = await download_thumbnail()
                            await app.send_document(m.chat.id, document=txt_filename,
                                caption=caption, thumb=thumb_path, parse_mode=ParseMode.HTML)

                            await progress_msg.edit_text(
                                "✅ <b>Extraction completed!</b>\n\n"
                                f"├─ Subjects: {total_subjects}\n"
                                f"├─ Links: {len(all_urls)}\n"
                                f"└─ Sent: ✅",
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as e:
                            logger.error(f"Error sending: {e}")
                            await progress_msg.edit_text(f"❌ Error sending: <code>{str(e)}</code>", parse_mode=ParseMode.HTML)
                        finally:
                            try:
                                os.remove(txt_filename)
                            except:
                                pass

                    except Exception as e:
                        logger.error(f"Error: {e}")
                        await progress_msg.edit_text(f"❌ Error: <code>{str(e)}</code>", parse_mode=ParseMode.HTML)

            except Exception as e:
                logger.error(f"Login error: {e}")
                await editable.edit_text(f"❌ <b>Login Failed</b>\n<code>{str(e)}</code>", parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error: {e}")
        await m.reply_text(f"❌ Error: <code>{str(e)}</code>", parse_mode=ParseMode.HTML)
