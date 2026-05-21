"""
Appx Master extractor module — Paid Appx with Login.
Adapted from ApnaEx-main/Extractor/modules/appex_v4.py.
Handles API URL input, user login (ID*Password or Token),
batch selection, and full course extraction. 
"""
import requests
import json
import os
import asyncio
import aiohttp
import logging
import time
import re
import cloudscraper
import base64
from base64 import b64decode
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from concurrent.futures import ThreadPoolExecutor
from pyrogram import filters
from pyrogram.types import Message
from datetime import datetime
import pytz
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

india_timezone = pytz.timezone('Asia/Kolkata')
THREADPOOL = ThreadPoolExecutor(max_workers=1000)
BOT_TEXT = getattr(Config, 'BOT_TEXT', 'Master Extractor')


def decrypt(enc):
    """Decrypt AES-CBC encrypted string (Appx standard)."""
    try:
        enc = b64decode(enc.split(':')[0])
        key = b'638udh3829162018'
        iv = b'fedcba9876543210'
        if len(enc) == 0:
            return ""
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(enc), AES.block_size)
        return plaintext.decode('utf-8')
    except:
        return ""


def decode_base64(encoded_str):
    try:
        return base64.b64decode(encoded_str).decode('utf-8')
    except:
        return encoded_str


async def fetch(session, url, headers):
    """Fetch URL and parse HTML-wrapped JSON response.
    Appx APIs often return JSON wrapped in HTML tags.
    Uses regex brace-matching to extract valid JSON."""
    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                logger.warning(f"HTTP {response.status} for {url}")
                return {}
            content = await response.text()
            # Try direct JSON parse first
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # HTML-wrapped JSON — find {"status": pattern and brace-match
                match = re.search(r'\{"status":', content, re.DOTALL)
                if match:
                    json_str = content[match.start():]
                    open_b = close_b = 0
                    json_end = -1
                    for i, char in enumerate(json_str):
                        if char == '{': open_b += 1
                        elif char == '}': close_b += 1
                        if open_b > 0 and open_b == close_b:
                            json_end = i + 1
                            break
                    if json_end != -1:
                        return json.loads(json_str[:json_end])
                logger.warning(f"Could not parse JSON from {url}")
                return {}
    except Exception as e:
        logger.error(f"Fetch error {url}: {e}")
        return {}


async def handle_course(session, api_base, bi, si, sn, topic, hdr1):
    """Process a single topic: fetch videos and extract URLs."""
    ti = topic.get("topicid")
    url = f"{api_base}/get/livecourseclassbycoursesubtopconceptapiv3?courseid={bi}&subjectid={si}&topicid={ti}&conceptid=&start=-1"
    r3 = await fetch(session, url, hdr1)
    video_data = sorted(r3.get("data", []), key=lambda x: x.get("id", 0))
    tasks = [process_video(session, api_base, bi, si, sn, ti, topic.get("topic_name", ""), video, hdr1) for video in video_data]
    results = await asyncio.gather(*tasks)
    return [line for lines in results if lines for line in lines]


async def process_video(session, api_base, bi, si, sn, ti, tn, video, hdr1):
    """Process a single video: extract all URLs (video, DRM, PDF)."""
    vi = video.get("id")
    vn = video.get("Title", "")
    lines = []

    try:
        r4 = await fetch(session, f"{api_base}/get/fetchVideoDetailsById?course_id={bi}&video_id={vi}&ytflag=0&folder_wise_course=0", hdr1)
        if not r4 or not r4.get("data"):
            return None

        data = r4["data"]
        vt = data.get("Title", vn)
        vl = data.get("download_link", "")
        fl = data.get("video_id", "")

        # YouTube video ID
        if fl:
            dfl = decrypt(fl)
            if dfl:
                lines.append(f"{vt}:https://youtu.be/{dfl}\n")

        # Direct download link
        if vl:
            dvl = decrypt(vl)
            if dvl and ".pdf" not in dvl:
                lines.append(f"{vt}:{dvl}\n")
        else:
            # Encrypted/DRM links
            encrypted_links = data.get("encrypted_links", [])
            if encrypted_links:
                first_link = encrypted_links[0]
                a = first_link.get("path")
                k = first_link.get("key")
                if a and k:
                    da = decrypt(a)
                    k1 = decrypt(k)
                    k2 = decode_base64(k1)
                    lines.append(f"{vt}:{da}*{k2}\n")
                elif a:
                    da = decrypt(a)
                    lines.append(f"{vt}:{da}\n")

        # Also try DRM MPD links
        drm_res = await fetch(session, f"{api_base}/get/get_mpd_drm_links?videoid={vi}&folder_wise_course=0", hdr1)
        if drm_res and drm_res.get('data'):
            drm_data = drm_res['data']
            if isinstance(drm_data, list) and drm_data and drm_data[0].get("path"):
                path = decrypt(drm_data[0]["path"])
                if path and not any(path in l for l in lines):
                    lines.append(f"{vt}:{path}\n")

        # PDF extraction (material_type == PDF or VIDEO with attached PDFs)
        mt = data.get("material_type", "")
        p1 = data.get("pdf_link", "")
        pk1 = data.get("pdf_encryption_key", "")
        p2 = data.get("pdf_link2", "")
        pk2 = data.get("pdf2_encryption_key", "")

        if p1:
            dp1 = decrypt(p1)
            if dp1:
                if pk1:
                    depk1 = decrypt(pk1)
                    if depk1 and depk1 != "abcdefg":
                        lines.append(f"{vt}:{dp1}*{depk1}\n")
                    else:
                        lines.append(f"{vt}:{dp1}\n")
                else:
                    lines.append(f"{vt}:{dp1}\n")
        if p2:
            dp2 = decrypt(p2)
            if dp2:
                if pk2:
                    depk2 = decrypt(pk2)
                    if depk2 and depk2 != "abcdefg":
                        lines.append(f"{vt}:{dp2}*{depk2}\n")
                    else:
                        lines.append(f"{vt}:{dp2}\n")
                else:
                    lines.append(f"{vt}:{dp2}\n")

        return lines
    except Exception as e:
        logger.error(f"Error processing video {vi}: {e}")
        return None


async def handle_app_paid(bot, message):
    """
    Main paid Appx handler — called from callback 'master'.
    Flow: API URL → Login → Batches → Extract → TXT file.
    """
    user_id = message.chat.id

    try:
        editable = await message.reply_text(
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 <b>Enter App API URL</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📝 <b>Instructions:</b>\n"
            "• Don't include https://\n"
            "• Only send domain name\n\n"
            "📌 <b>Example:</b>\n"
            "<code>tcsexamzoneapi.classx.co.in</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )

        input1 = await bot.listen(chat_id=user_id)
        api_txt = input1.text.strip()
        await input1.delete()

        if "api" not in api_txt.lower() and not api_txt.startswith("http"):
            await editable.edit("❌ Invalid API URL. Must contain 'api' in the domain.\nExample: `tcsexamzoneapi.classx.co.in`")
            return

        api_base = api_txt if api_txt.startswith("http") else f"https://{api_txt}"
        api_base = api_base.rstrip("/")
        app_name = api_base.replace("https://", "").replace("http://", "").replace("api.classx.co.in", "").replace("api.appx.co.in", "").replace("api.akamai.net.in", "").replace("/", "").strip()

        await editable.edit(
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔐 <b>Login Required</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣ <b>Use ID & Password:</b>\n"
            "   <code>ID*Password</code>\n\n"
            "2️⃣ <b>Or use Token directly:</b>\n"
            "   <code>eyJhbGciOi...</code>\n\n"
            "📌 <b>Example:</b>\n"
            "• ID/Pass ➠ <code>9769696969*password123</code>\n"
            "• Token ➠ <code>eyJhbGciOiJIUzI1...</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )

        input2 = await bot.listen(chat_id=user_id)
        raw_text = input2.text.strip()
        await input2.delete()

        token = None
        userid = None

        if '*' in raw_text:
            # Login with ID*Password
            email, password = raw_text.split("*", 1)
            login_headers = {
                "Auth-Key": "appxapi",
                "User-Id": "-2",
                "Authorization": "",
                "User_app_category": "",
                "Language": "en",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept-Encoding": "gzip, deflate",
                "User-Agent": "okhttp/4.9.1"
            }
            login_data = {"email": email, "password": password}

            try:
                response = requests.post(f"{api_base}/post/userLogin", data=login_data, headers=login_headers).json()
                status = response.get("status")

                if status == 200:
                    userid = response["data"]["userid"]
                    token = response["data"]["token"]
                elif status == 203:
                    # Try website login method
                    web_headers = {
                        "auth-key": "appxapi",
                        "client-service": "Appx",
                        "source": "website",
                        "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
                        "accept": "*/*"
                    }
                    web_data = {
                        "source": "website",
                        "phone": email,
                        "email": email,
                        "password": password,
                        "extra_details": "1"
                    }
                    r2 = requests.post(f"{api_base}/post/userLogin?extra_details=0", headers=web_headers, data=web_data).json()
                    if r2.get("status") == 200:
                        userid = r2["data"]["userid"]
                        token = r2["data"]["token"]
                    else:
                        await editable.edit(f"❌ Login Failed!\n\nStatus: {r2.get('status')}\n{r2.get('message', 'Unknown error')}")
                        return
                else:
                    await editable.edit(f"❌ Login Failed!\n\nStatus: {status}\n{response.get('message', 'Unknown error')}")
                    return
            except Exception as e:
                await editable.edit(f"❌ Login Error: {str(e)}")
                return
        else:
            # Direct token
            token = raw_text
            userid = "1234"

        # Build auth headers
        hdr1 = {
            "Client-Service": "Appx",
            "source": "website",
            "Auth-Key": "appxapi",
            "Authorization": token,
            "User-ID": str(userid)
        }

        await editable.edit("✅ Login successful! Fetching your batches...")

        # Fetch user's purchased batches
        scraper = cloudscraper.create_scraper()
        try:
            mc1 = scraper.get(f"{api_base}/get/mycoursev2?userid={userid}", headers=hdr1).json()
        except Exception as e:
            await editable.edit(f"❌ Error fetching batches: {str(e)}")
            return

        if not mc1.get("data"):
            await editable.edit("❌ No batches found! Check if your login is correct.")
            return

        # Display batch list
        batch_list = ""
        valid_ids = []
        for ct in mc1["data"]:
            ci = ct.get("id")
            cn = ct.get("course_name")
            price = ct.get("price", "N/A")
            batch_list += f"┣━➤ <code>{ci}</code>\n┃   <b>{cn}</b>\n┃   💰 ₹{price}\n┃\n"
            valid_ids.append(str(ci))

        batch_info = (
            f"✅ <b>Login Successful!</b>\n\n"
            f"📡 <b>API:</b> <code>{api_base}</code>\n\n"
            f"📚 <b>Your Batches:</b>\n{batch_list}\n\n"
            f"Send batch ID(s) to extract.\n"
            f"Multiple: separate with <code>&</code>\n"
            f"Copy all: <code>{'&'.join(valid_ids)}</code>"
        )

        if len(batch_info) > 4000:
            fname = f"{user_id}_batches.txt"
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(batch_info)
            await editable.delete()
            await message.reply_document(document=fname, caption=f"📚 {len(valid_ids)} batches found. Send batch ID(s).")
            try:
                os.remove(fname)
            except:
                pass
        else:
            await editable.edit(batch_info)

        input3 = await bot.listen(chat_id=user_id)
        batch_input = input3.text.strip()
        await input3.delete()

        batch_ids = [b.strip() for b in batch_input.split("&") if b.strip() in valid_ids]
        if not batch_ids:
            await message.reply_text("❌ Invalid batch ID(s). Send valid IDs from the list.")
            return

        # Process each batch
        for raw_batch_id in batch_ids:
            course_info = next((ct for ct in mc1["data"] if str(ct.get("id")) == raw_batch_id), {})
            course_name = course_info.get("course_name", "Course")
            thumbnail = course_info.get("course_thumbnail", "")
            price = course_info.get("price", "N/A")

            status_msg = await message.reply_text(f"🔄 Extracting: <code>{course_name}</code>")
            start_time = time.time()
            clean_name = course_name.replace('/', '-').replace('|', '-').replace(':', '-')[:200]
            filename = f"{user_id}_{raw_batch_id}_{clean_name}.txt"

            try:
                from module.appxfree import (
                    fetch_appx_html_to_json, process_folder_wise_course_0, 
                    process_folder_wise_course_1
                )
                connector = aiohttp.TCPConnector(limit=100)
                async with aiohttp.ClientSession(connector=connector) as session:
                    # First check folder_wise_course flag from course info
                    folder_wise = course_info.get("folder_wise_course", "")
                    
                    all_outputs = []
                    
                    if folder_wise == 0 or folder_wise == "0":
                        logger.info(f"Batch {raw_batch_id}: folder_wise_course=0 (subject→topic→video)")
                        all_outputs = await process_folder_wise_course_0(session, api_base, raw_batch_id, hdr1, user_id)
                    elif folder_wise == 1 or folder_wise == "1":
                        logger.info(f"Batch {raw_batch_id}: folder_wise_course=1 (folder-based)")
                        all_outputs = await process_folder_wise_course_1(session, api_base, raw_batch_id, hdr1, user_id)
                    else:
                        # Unknown or missing — try both methods
                        logger.info(f"Batch {raw_batch_id}: folder_wise_course={folder_wise}, trying both methods")
                        outputs_0 = await process_folder_wise_course_0(session, api_base, raw_batch_id, hdr1, user_id)
                        all_outputs.extend(outputs_0)
                        outputs_1 = await process_folder_wise_course_1(session, api_base, raw_batch_id, hdr1, user_id)
                        all_outputs.extend(outputs_1)
                    
                    if all_outputs:
                        with open(filename, 'w', encoding='utf-8') as f:
                            for line in all_outputs:
                                f.write(line)
                    else:
                        await status_msg.edit("❌ No content found in this batch. The course may be empty or use an unsupported format.")
                        continue

                # Check if file has content
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    end_time = time.time()
                    elapsed = end_time - start_time
                    mins = int(elapsed // 60)
                    secs = int(elapsed % 60)
                    formatted_time = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                    time_new = datetime.now(india_timezone).strftime("%d-%m-%Y %I:%M %p")

                    # Count links
                    with open(filename, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    total = len(lines)

                    caption = (
                        f"🎓 <b>COURSE EXTRACTED</b> 🎓\n\n"
                        f"📱 <b>APP:</b> {app_name}\n"
                        f"📚 <b>BATCH:</b> {course_name}\n"
                        f"💰 <b>PRICE:</b> ₹{price}\n"
                        f"⏱ <b>TIME:</b> {formatted_time}\n"
                        f"📅 <b>DATE:</b> {time_new} IST\n\n"
                        f"📊 <b>STATS</b>\n"
                        f"├─ 📁 Total Links: {total}\n"
                        f"└─ ⏱ {formatted_time}\n\n"
                        f"🚀 <b>By:</b> @{(await bot.get_me()).username}\n\n"
                        f"<code>╾───• {BOT_TEXT} •───╼</code>"
                    )

                    try:
                        await status_msg.delete()
                        await message.reply_document(
                            document=filename,
                            caption=caption,
                            file_name=f"{clean_name}.txt"
                        )
                    except Exception as e:
                        logger.error(f"Send error: {e}")
                else:
                    await status_msg.edit("❌ No content found in this batch.")
            except Exception as e:
                logger.error(f"Batch {raw_batch_id} error: {e}")
                await status_msg.edit(f"❌ Error: {str(e)}")
            finally:
                try:
                    os.remove(filename)
                except:
                    pass

    except Exception as e:
        logger.error(f"Appx master error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")
