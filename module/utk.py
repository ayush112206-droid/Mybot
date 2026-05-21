"""
Utkarsh extractor module.
Adapted from ApnaEx-main/Extractor/modules/utk.py
"""
import requests
import datetime
import pytz
import re
import aiofiles
import os
import base64
import asyncio
import time
import json
import aiohttp
import logging
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from base64 import b64decode
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

appname = "Utkarsh"
MAX_CONCURRENT_REQUESTS = 1000
MAX_RETRIES = 15
TIMEOUT = 90
UPDATE_DELAY = 5
SESSION_TIMEOUT = 200
MAX_WORKERS = 5000
UPDATE_INTERVAL = 15
CHECKPOINT_FILE = "batch_checkpoint.json"
EDIT_LOCK = asyncio.Lock()


async def safe_edit_message(message, text):
    """Safely edit a message with retry logic and delay"""
    async with EDIT_LOCK:
        for attempt in range(MAX_RETRIES):
            try:
                await asyncio.sleep(UPDATE_DELAY)
                await message.edit(text)
                return True
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"Failed to edit message: {e}")
                    return False
                await asyncio.sleep(UPDATE_DELAY * 2)
        return False


def decrypt(enc):
    enc = b64decode(enc)
    Key = '%!$!%_$&!%F)&^!^'.encode('utf-8')
    iv = '#*y*#2yJ*#$wJv*v'.encode('utf-8')
    cipher = AES.new(Key, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(enc), AES.block_size)
    return plaintext.decode('utf-8')


async def handle_utk_logic(app, m):
    """Main Utkarsh handler - called from __init__.py callback"""
    txt_dump = CHANNEL_ID
    start_time = time.time()

    editable = await m.reply_text(
        "🔹 <b>UTK EXTRACTOR PRO</b> 🔹\n\n"
        "Send **ID & Password** in this format: <code>ID*Password</code>"
    )

    input1 = await app.listen(chat_id=m.chat.id)
    raw_text = input1.text
    await input1.delete()

    for attempt in range(MAX_RETRIES):
        try:
            token_response = requests.get('https://online.utkarsh.com/web/home/get_states', timeout=TIMEOUT)
            token = token_response.json()["token"]
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2)
                continue
            else:
                await safe_edit_message(editable, "❌ Failed to connect to Utkarsh servers.")
                return

    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'origin': 'https://online.utkarsh.com',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'en-US,en;q=0.9',
        'cookie': f'csrf_name={token}; ci_session=tb0uld02neaa4ujs1g4idb6l8bmql8jh'
    }

    if '*' in raw_text:
        ids, ps = raw_text.split("*")
        data = f"csrf_name={token}&mobile={ids}&url=0&password={ps}&submit=LogIn&device_token=null"

        try:
            log_response = requests.post(
                'https://online.utkarsh.com/web/Auth/login',
                headers=headers, data=data, timeout=TIMEOUT
            ).json()["response"].replace('MDE2MTA4NjQxMDI3NDUxNQ==', '==').replace(':', '==')
            dec_log = decrypt(log_response)
            dec_logs = json.loads(dec_log)
            error_message = dec_logs["message"]
            status = dec_logs['status']

            if status:
                await safe_edit_message(editable, "✅ <b>Authentication successful!</b>")
            else:
                await safe_edit_message(editable, f'❌ Login Failed - {error_message}')
                return
        except Exception as e:
            await safe_edit_message(editable, f'❌ Error during login: {str(e)}')
            return
    else:
        await safe_edit_message(editable, "❌ <b>Invalid format!</b>\n\nPlease use: <code>ID*Password</code>")
        return

    try:
        data2 = "type=Batch&csrf_name=" + token + "&sort=0"
        res2 = requests.post(
            'https://online.utkarsh.com/web/Profile/my_course',
            headers=headers, data=data2, timeout=TIMEOUT
        ).json()["response"].replace('MDE2MTA4NjQxMDI3NDUxNQ==', '==').replace(':', '==')
        decrypted_res = decrypt(res2)
        dc = json.loads(decrypted_res)
        dataxxx = dc['data']
        bdetail = dataxxx.get("data", [])

        if not bdetail:
            await safe_edit_message(editable, "❌ No courses found.")
            return

        cool = ""
        Batch_ids = ''

        for item in bdetail:
            id_val = item.get("id")
            batch = item.get("title")
            price = item.get("mrp")
            aa = f"<code>{id_val}</code> - <b>{batch}</b> 💰 ₹{price}\n\n"
            if len(f'{cool}{aa}') > 4096:
                cool = ""
            cool += aa
            Batch_ids += str(id_val) + '&'
        Batch_ids = Batch_ids.rstrip('&')

        login_msg = f'<b>✅ {appname} Login Successful</b>\n'
        login_msg += f'\n<b>🆔 Credentials:</b> <code>{raw_text}</code>\n\n'
        login_msg += f'\n\n<b>📚 Available Batches</b>\n\n{cool}'

        if txt_dump:
            try:
                await app.send_message(txt_dump, login_msg)
            except:
                pass

        await safe_edit_message(editable, f'🔸 <b>BATCH INFORMATION</b> 🔸\n\n{cool}')

        editable1 = await m.reply_text(
            f"<b>📥 Send the Batch ID to download</b>\n\n"
            f"<b>💡 For ALL batches:</b> <code>{Batch_ids}</code>\n\n"
            f"<i>Supports multiple IDs separated by '&'</i>"
        )

        user_id = int(m.chat.id)
        input2 = await app.listen(chat_id=m.chat.id)
        await input2.delete()
        await editable.delete()
        await editable1.delete()

        if "&" in input2.text:
            batch_ids = input2.text.split('&')
        else:
            batch_ids = [input2.text]

        for batch_id in batch_ids:
            batch_id = batch_id.strip()
            start_time_batch = datetime.datetime.now()
            progress_msg = await m.reply_text(f"⏳ <b>Processing batch ID:</b> <code>{batch_id}</code>...")

            bname = next((x['title'] for x in bdetail if str(x['id']) == batch_id), None)
            if not bname:
                await safe_edit_message(progress_msg, f"❌ Batch ID <code>{batch_id}</code> not found!")
                continue

            try:
                data4 = {
                    'tile_input': f'{{"course_id": {batch_id},"revert_api":"1#0#0#1","parent_id":0,"tile_id":"0","layer":1,"type":"course_combo"}}',
                    'csrf_name': token
                }
                Key = '%!$!%_$&!%F)&^!^'.encode('utf-8')
                iv = '#*y*#2yJ*#$wJv*v'.encode('utf-8')
                cipher = AES.new(Key, AES.MODE_CBC, iv)
                padded_data = pad(data4['tile_input'].encode(), AES.block_size)
                encrypted_data = cipher.encrypt(padded_data)
                encoded_data = base64.b64encode(encrypted_data).decode()
                data4['tile_input'] = encoded_data

                res4 = requests.post(
                    "https://online.utkarsh.com/web/Course/tiles_data",
                    headers=headers, data=data4, timeout=TIMEOUT
                ).json()["response"].replace('MDE2MTA4NjQxMDI3NDUxNQ==', '==').replace(':', '==')
                res4_dec = decrypt(res4)
                res4_json = json.loads(res4_dec)
                subject = res4_json.get("data", [])

                if not subject:
                    await safe_edit_message(progress_msg, f"❌ No subjects in batch <code>{batch_id}</code>")
                    continue

                subject_ids = [id_item["id"] for id_item in subject]

                all_urls = await process_batch_subjects(
                    app, subject_ids, subject, batch_id,
                    headers, token, progress_msg, bname
                )

                if all_urls:
                    await _send_utk_result(
                        app, user_id, m, all_urls,
                        start_time_batch, bname, batch_id,
                        progress_msg, txt_dump
                    )
                else:
                    await safe_edit_message(progress_msg, f"⚠️ No content URLs found in <code>{bname}</code>")
            except Exception as e:
                await safe_edit_message(progress_msg, f"❌ Error: {str(e)}")

        try:
            requests.get("https://online.utkarsh.com/web/Auth/logout", headers=headers, timeout=TIMEOUT)
        except:
            pass

    except Exception as e:
        await safe_edit_message(editable, f"❌ Error: {str(e)}")


async def update_progress_safely(progress_msg, text, last_update_time, min_interval=UPDATE_INTERVAL):
    current_time = time.time()
    if current_time - last_update_time >= min_interval:
        try:
            await progress_msg.edit(text)
            return current_time
        except:
            pass
    return last_update_time


async def process_single_subject(app, subject_id, subject_list, batch_id, headers, token, progress_msg, current_subject, total_subjects):
    topicName = next((x['title'] for x in subject_list if str(x['id']) == str(subject_id)), "Unknown")
    start_time = time.time()
    last_update_time = 0

    try:
        data5 = {
            'tile_input': f'{{"course_id":{subject_id},"layer":1,"page":1,"parent_id":{batch_id},"revert_api":"1#0#0#1","tile_id":"0","type":"content"}}',
            'csrf_name': token
        }
        Key = '%!$!%_$&!%F)&^!^'.encode('utf-8')
        iv = '#*y*#2yJ*#$wJv*v'.encode('utf-8')
        cipher = AES.new(Key, AES.MODE_CBC, iv)
        padded_data = pad(data5['tile_input'].encode(), AES.block_size)
        encrypted_data = cipher.encrypt(padded_data)
        encoded_data = base64.b64encode(encrypted_data).decode()
        data5['tile_input'] = encoded_data

        res5 = requests.post(
            "https://online.utkarsh.com/web/Course/tiles_data",
            headers=headers, data=data5, timeout=TIMEOUT
        ).json()["response"].replace('MDE2MTA4NjQxMDI3NDUxNQ==', '==').replace(':', '==')

        decres5 = decrypt(res5)
        res5l = json.loads(decres5)
        resp5 = res5l.get("data", {})

        if not resp5:
            return []

        res5list = resp5.get("list", [])
        topic_ids = [str(id_item["id"]) for id_item in res5list]

        all_topic_urls = []
        total_topics = len(topic_ids)
        processed_topics = 0
        last_update_time = time.time()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            chunk_size = 5
            for i in range(0, len(topic_ids), chunk_size):
                chunk = topic_ids[i:i + chunk_size]
                futures = []

                for t in chunk:
                    future = executor.submit(
                        process_topic, subject_id, t, batch_id, headers, token, Key, iv
                    )
                    futures.append(future)

                for future in as_completed(futures):
                    try:
                        topic_urls = future.result()
                        if topic_urls:
                            all_topic_urls.extend(topic_urls)
                        processed_topics += 1
                        current_time = time.time()
                        if current_time - last_update_time >= UPDATE_INTERVAL:
                            elapsed = current_time - start_time
                            eta = (elapsed / processed_topics) * (total_topics - processed_topics) if processed_topics > 0 else 0
                            progress_text = (
                                f"🔄 <b>Processing</b>\n"
                                f"├─ Subject: {current_subject}/{total_subjects}\n"
                                f"├─ Name: <code>{topicName}</code>\n"
                                f"├─ Topics: {processed_topics}/{total_topics}\n"
                                f"├─ Links: {len(all_topic_urls)}\n"
                                f"├─ Time: {str(timedelta(seconds=int(elapsed)))}\n"
                                f"└─ ETA: {str(timedelta(seconds=int(eta)))}"
                            )
                            last_update_time = await update_progress_safely(progress_msg, progress_text, last_update_time)
                    except Exception as e:
                        logger.error(f"Topic error: {e}")
                        continue

                await asyncio.sleep(1)

        return all_topic_urls

    except Exception as e:
        logger.error(f"Subject error {topicName}: {e}")
        return []


def process_topic(subject_id, topic_id, batch_id, headers, token, Key, iv):
    """Process a single topic (runs in thread)."""
    try:
        data5 = {
            'tile_input': f'{{"course_id":{subject_id},"parent_id":{batch_id},"layer":2,"page":1,"revert_api":"1#0#0#1","subject_id":{topic_id},"tile_id":0,"topic_id":{topic_id},"type":"content"}}',
            'csrf_name': token
        }

        cipher = AES.new(Key, AES.MODE_CBC, iv)
        padded_data = pad(data5['tile_input'].encode(), AES.block_size)
        encrypted_data = cipher.encrypt(padded_data)
        encoded_data = base64.b64encode(encrypted_data).decode()
        data5['tile_input'] = encoded_data

        res6 = requests.post(
            "https://online.utkarsh.com/web/Course/tiles_data",
            headers=headers, data=data5, timeout=TIMEOUT
        ).json()["response"].replace('MDE2MTA4NjQxMDI3NDUxNQ==', '==').replace(':', '==')

        decres6 = decrypt(res6)
        res6l = json.loads(decres6)
        resp5 = res6l.get("data", {})

        if not resp5:
            return []

        res6list = resp5.get("list", [])
        topic_idss = [str(id_item["id"]) for id_item in res6list]

        topic_urls = []
        for tt in topic_idss:
            try:
                data6 = {
                    'layer_two_input_data': f'{{"course_id":{subject_id},"parent_id":{batch_id},"layer":3,"page":1,"revert_api":"1#0#0#1","subject_id":{topic_id},"tile_id":0,"topic_id":{tt},"type":"content"}}',
                    'content': 'content',
                    'csrf_name': token
                }
                encoded_data = base64.b64encode(data6['layer_two_input_data'].encode()).decode()
                data6['layer_two_input_data'] = encoded_data

                res6 = requests.post(
                    "https://online.utkarsh.com/web/Course/get_layer_two_data",
                    headers=headers, data=data6, timeout=TIMEOUT
                ).json()["response"].replace('MDE2MTA4NjQxMDI3NDUxNQ==', '==').replace(':', '==')

                decres6 = decrypt(res6)
                res6_json = json.loads(decres6)
                res6data = res6_json.get('data', {})

                if not res6data:
                    continue

                res6_list = res6data.get('list', [])
                for item in res6_list:
                    title = item.get("title", "").replace("||", "-").replace(":", "-")
                    bitrate_urls = item.get("bitrate_urls", [])
                    url = None

                    for url_data in bitrate_urls:
                        if url_data.get("title") == "720p":
                            url = url_data.get("url")
                            break
                        elif url_data.get("name") == "720x1280.mp4":
                            url = url_data.get("link") + ".mp4"
                            url = url.replace("/enc/", "/plain/")

                    if url is None:
                        url = item.get("file_url")

                    if url and not url.endswith('.ws'):
                        if url.endswith(("_0_0", "_0")):
                            url = "https://apps-s3-jw-prod.utkarshapp.com/admin_v1/file_library/videos/enc_plain_mp4/{}/plain/720x1280.mp4".format(url.split("_")[0])
                        elif not url.startswith("https://") and not url.startswith("http://"):
                            url = f"https://youtu.be/{url}"
                        cc = f'{title}: {url}'
                        topic_urls.append(cc)

            except Exception as e:
                logger.error(f"Subtopic error {tt}: {e}")
                continue

        return topic_urls

    except Exception as e:
        logger.error(f"Topic error {topic_id}: {e}")
        return []


async def process_batch_subjects(app, subject_ids, subject_list, batch_id, headers, token, progress_msg, bname):
    all_urls = []
    total_subjects = len(subject_ids)
    batch_start_time = time.time()
    last_update_time = 0

    for idx, subject_id in enumerate(subject_ids, 1):
        try:
            subject_urls = await process_single_subject(
                app, subject_id, subject_list, batch_id,
                headers, token, progress_msg, idx, total_subjects
            )
            if subject_urls:
                all_urls.extend(subject_urls)

            current_time = time.time()
            if current_time - last_update_time >= UPDATE_INTERVAL:
                elapsed = current_time - batch_start_time
                eta = (elapsed / idx) * (total_subjects - idx) if idx > 0 else 0
                progress_text = (
                    f"📦 <b>Large Batch Progress</b>\n"
                    f"├─ Completed: {idx}/{total_subjects}\n"
                    f"├─ Links: {len(all_urls)}\n"
                    f"├─ Time: {str(timedelta(seconds=int(elapsed)))}\n"
                    f"└─ ETA: {str(timedelta(seconds=int(eta)))}"
                )
                last_update_time = await update_progress_safely(progress_msg, progress_text, last_update_time)

            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Subject error: {e}")
            continue

    return all_urls


async def sanitize_bname(bname, max_length=50):
    if not bname:
        return "Unknown_Batch"
    bname = re.sub(r'[\\/:*?"<>|\t\n\r]+', '', bname).strip()
    bname = bname.replace(' ', '_')
    if len(bname) > max_length:
        bname = bname[:max_length]
    bname = ''.join(c for c in bname if ord(c) < 128)
    if not bname:
        bname = "Unknown_Batch"
    return bname


async def _send_utk_result(app, user_id, m, all_urls, start_time, bname, batch_id, progress_msg, txt_dump):
    """Format and send the extraction result."""
    THUMB_URL = getattr(Config, 'THUMB_URL', '')
    BOT_TEXT = getattr(Config, 'BOT_TEXT', 'Master Extractor')

    try:
        bname = await sanitize_bname(bname)
        file_path = f"{bname}.txt"

        await safe_edit_message(progress_msg, "💾 Creating file...")

        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.writelines([url + '\n' for url in all_urls])

        video_count = len([u for u in all_urls if any(ext in u.lower() for ext in ['.mp4', '.m3u8', '.mpd', 'youtu.be'])])
        pdf_count = len([u for u in all_urls if '.pdf' in u.lower()])

        local_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        minutes, seconds = divmod(duration.total_seconds(), 60)

        caption = (
            f"🎓 <b>COURSE EXTRACTED</b> 🎓\n\n"
            f"📱 <b>APP:</b> {appname}\n"
            f"📚 <b>BATCH:</b> {bname} (ID: {batch_id})\n"
            f"⏱ <b>TIME:</b> {int(minutes):02d}:{int(seconds):02d}\n"
            f"📅 <b>DATE:</b> {local_time.strftime('%d-%m-%Y %H:%M:%S')} IST\n\n"
            f"📊 <b>STATS</b>\n"
            f"├─ 📁 Total: {len(all_urls)}\n"
            f"├─ 🎬 Videos: {video_count}\n"
            f"├─ 📄 PDFs: {pdf_count}\n"
            f"└─ 📦 Others: {len(all_urls) - video_count - pdf_count}\n\n"
            f"🚀 <b>By:</b> @{(await app.get_me()).username}\n\n"
            f"<code>╾───• {BOT_TEXT} •───╼</code>"
        )

        await safe_edit_message(progress_msg, "📤 Uploading...")

        try:
            thumb_path = None
            if THUMB_URL:
                thumb_path = f"thumb_{bname}.jpg"
                async with aiofiles.open(thumb_path, 'wb') as f:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(THUMB_URL) as response:
                            await f.write(await response.read())

            if thumb_path and os.path.exists(thumb_path):
                await m.reply_document(document=file_path, caption=caption, thumb=thumb_path)
                if txt_dump:
                    try:
                        await app.send_document(txt_dump, file_path, caption=caption, thumb=thumb_path)
                    except:
                        pass
                os.remove(thumb_path)
            else:
                await m.reply_document(document=file_path, caption=caption)
                if txt_dump:
                    try:
                        await app.send_document(txt_dump, file_path, caption=caption)
                    except:
                        pass

            os.remove(file_path)
            await progress_msg.delete()

        except Exception as e:
            await safe_edit_message(progress_msg, f"❌ Error sending: {str(e)}")

    except Exception as e:
        await safe_edit_message(progress_msg, f"❌ Error: {str(e)}")
