"""
Study IQ extractor module.
Adapted from ApnaEx-main/Extractor/modules/iq.py
"""
import requests
import datetime
import pytz
import re
import aiofiles
import os
import aiohttp
from pyrogram import Client
from pyrogram.types import Message
from config import Config
import logging

logger = logging.getLogger(__name__)


async def fetchs(url, json=None, headers=None):
    async with aiohttp.ClientSession() as session:
        if json:
            async with session.post(url, json=json, headers=headers) as response:
                return await response.json()
        else:
            async with session.get(url, headers=headers) as response:
                return await response.json()


def sync_get(url, headers=None):
    """Synchronous GET request (replaces server.get)"""
    try:
        response = requests.get(url, headers=headers, timeout=90)
        return response.json()
    except Exception as e:
        logger.error(f"sync_get error: {e}")
        return {}


async def handle_iq_logic(app, m):
    """Main Study IQ handler - called from __init__.py callback"""
    BOT_TEXT = getattr(Config, 'BOT_TEXT', 'Master Extractor')
    try:
        editable = await m.reply_text(
            "🔹 <b>STUDY IQ EXTRACTOR PRO</b> 🔹\n\n"
            "Send your <b>Phone Number</b> to login\n"
            "Or directly use your saved <b>Token</b>\n\n"
            "📱 <b>Phone:</b> <code>10-digit number</code>\n"
            "🔑 <b>Token:</b> <code>your_saved_token</code>\n\n"
            "<i>Example:</i>\n"
            "Phone: <code>9876543210</code>\n"
            "Token: <code>eyJhbGciOiJ...</code>\n\n"
            "💡 <i>Use token to login instantly without OTP</i>"
        )

        input1 = await app.listen(chat_id=m.chat.id)
        await input1.delete()
        raw_text1 = input1.text.strip()
        logged_in = False

        if raw_text1.isdigit():
            phNum = raw_text1.strip()
            master0 = await fetchs("https://www.studyiq.net/api/web/userlogin", json={"mobile": phNum})
            msg = master0.get('msg')

            if master0.get('data'):
                user_id = master0.get('data', {}).get('user_id')
                await editable.edit_text(
                    "✅ <b>OTP Sent Successfully</b>\n\n"
                    f"📱 Phone: <code>{phNum}</code>\n"
                    "📬 Please check your messages and send the OTP"
                )
            else:
                await editable.edit_text(
                    "❌ <b>Login Failed</b>\n\n"
                    f"Error: {msg}\n\n"
                    "Please check your number and try again."
                )
                return

            input2 = await app.listen(chat_id=m.chat.id)
            raw_text2 = input2.text.strip()
            otp = raw_text2
            await input2.delete()

            data = {"user_id": user_id, "otp": otp}
            master1 = await fetchs("https://www.studyiq.net/api/web/web_user_login", json=data)
            msg = master1.get('msg')

            if master1.get('data'):
                token = master1.get('data', {}).get('api_token')
                if token:
                    await editable.edit_text(
                        "✅ <b>Login Successful</b>\n\n"
                        f"🔑 Your Access Token:\n<code>{token}</code>\n\n"
                        "<i>Save this token for future logins</i>"
                    )
                    logged_in = True
                else:
                    await editable.edit_text(f"❌ <b>Login Failed</b>\n\nError: {msg}")
                    return
        else:
            token = raw_text1.strip()
            logged_in = True

        if logged_in:
            headers = {"Authorization": f"Bearer {token}"}

            json_master2 = sync_get(
                "https://backend.studyiq.net/app-content-ws/api/v1/getAllPurchasedCourses?source=WEB",
                headers=headers
            )

            if not json_master2.get('data'):
                await editable.edit_text("❌ <b>No Batches Found</b>")
                return

            Batch_ids = []
            batch_text = ""
            for course in json_master2["data"]:
                batch_id = course['courseId']
                name = course['courseTitle']
                batch_text += f"<code>{batch_id}</code> - <b>{name}</b> 💰\n\n"
                Batch_ids.append(str(batch_id))

            await editable.edit_text(
                f"✅ <b>Login Successful!</b>\n\n"
                f"📚 <b>Available Batches:</b>\n\n{batch_text}"
            )

            Batch_ids_str = '&'.join(Batch_ids)
            editable1 = await m.reply_text(
                "<b>📥 Send the Batch ID to download</b>\n\n"
                f"<b>💡 For ALL batches:</b> <code>{Batch_ids_str}</code>\n\n"
                "<i>Supports multiple IDs separated by '&'</i>"
            )

            input4 = await app.listen(chat_id=m.chat.id)
            await input4.delete()
            await editable.delete()
            await editable1.delete()

            if "&" in input4.text:
                batch_ids = input4.text.split('&')
            else:
                batch_ids = [input4.text]

            for batch_id in batch_ids:
                batch_id = batch_id.strip()
                start_time = datetime.datetime.now()
                progress_msg = await m.reply_text(
                    "🔄 <b>Processing Large Batch</b>\n"
                    f"└─ Initializing batch: <code>{batch_id}</code>"
                )

                if batch_id:
                    master3 = sync_get(
                        f"https://backend.studyiq.net/app-content-ws/v1/course/getDetails?courseId={batch_id}&languageId=",
                        headers=headers
                    )
                    bname = master3.get("courseTitle", "").replace(' || ', '').replace('|', '')

                    if not bname:
                        await progress_msg.edit_text("❌ <b>Invalid batch ID</b>")
                        continue

                    all_urls = []
                    content_ids = [str(item.get("contentId")) for item in master3.get('data', [])]

                    for t_id in content_ids:
                        topicname = next(
                            (x.get('name') for x in master3.get('data', []) if x.get('contentId') == int(t_id)),
                            None
                        )
                        try:
                            await progress_msg.edit(f"⏳ **Processing:** `{topicname}`")
                        except:
                            pass

                        parent_data = sync_get(
                            f"https://backend.studyiq.net/app-content-ws/v1/course/getDetails?courseId={batch_id}&languageId=&parentId={t_id}",
                            headers=headers
                        )
                        subFolderOrderId = [item.get("subFolderOrderId") for item in parent_data.get('data', [])]

                        if all(s is None for s in subFolderOrderId):
                            for video_item in parent_data.get('data', []):
                                url = video_item.get('videoUrl')
                                name = video_item.get('name')
                                if url:
                                    cc = f"[{topicname}]-{name}:{url}"
                                    all_urls.append(cc)
                                contentIdy = video_item.get('contentId')
                                try:
                                    response = await fetchs(
                                        f"https://backend.studyiq.net/app-content-ws/api/lesson/data?lesson_id={contentIdy}&courseId={batch_id}",
                                        headers=headers
                                    )
                                    for option in response.get('options', []):
                                        if option.get('urls'):
                                            for url_data in option['urls']:
                                                if 'name' in url_data:
                                                    name = url_data['name']
                                                    url = url_data['url']
                                                    cc = f"[Notes] - {name}: {url}"
                                                    all_urls.append(cc)
                                except:
                                    pass
                        else:
                            content_idx = [str(item.get("contentId")) for item in parent_data.get('data', [])]
                            for p_id in content_idx:
                                course_title = next(
                                    (x.get('name') for x in parent_data.get('data', []) if x.get('contentId') == int(p_id)),
                                    None
                                )
                                video = sync_get(
                                    f"https://backend.studyiq.net/app-content-ws/v1/course/getDetails?courseId={batch_id}&languageId=&parentId={t_id}/{p_id}",
                                    headers=headers
                                )
                                for video_item in video.get('data', []):
                                    url = video_item.get('videoUrl')
                                    name = video_item.get('name')
                                    if url:
                                        cc = f"[{course_title}]-{name}:{url}"
                                        all_urls.append(cc)
                                    contentIdx = video_item.get('contentId')
                                    try:
                                        response = await fetchs(
                                            f"https://backend.studyiq.net/app-content-ws/api/lesson/data?lesson_id={contentIdx}&courseId={batch_id}",
                                            headers=headers
                                        )
                                        for option in response.get('options', []):
                                            if option.get('urls'):
                                                for url_data in option['urls']:
                                                    if 'name' in url_data:
                                                        name = url_data['name']
                                                        url = url_data['url']
                                                        cc = f"[Notes] - {name}: {url}"
                                                        all_urls.append(cc)
                                    except:
                                        pass

                    await progress_msg.edit('**URL Writing Successful**')
                    await progress_msg.delete()

                    if all_urls:
                        await _send_result(app, m, all_urls, start_time, bname, batch_id, BOT_TEXT)
                    else:
                        await m.reply("❌ **No URLs found**")

    except Exception as e:
        await m.reply_text(
            "❌ <b>An error occurred</b>\n\n"
            f"Error details: <code>{str(e)}</code>\n\n"
            "Please try again or contact support."
        )


async def _send_result(app, m, all_urls, start_time, bname, batch_id, BOT_TEXT):
    """Format and send the extraction result."""
    bname = re.sub(r'[\\/:*?"<>|\t\n\r]+', '', bname).strip()
    if len(bname) > 50:
        bname = bname[:50]
    file_path = f"{bname}.txt"

    local_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    minutes, seconds = divmod(duration.total_seconds(), 60)

    all_text = "\n".join(all_urls)
    video_count = len(re.findall(r'\.(m3u8|mpd|mp4)', all_text))
    pdf_count = len(re.findall(r'\.pdf', all_text))

    caption = (
        f"🎓 <b>COURSE EXTRACTED</b> 🎓\n\n"
        f"📱 <b>APP:</b> Study IQ\n"
        f"📚 <b>BATCH:</b> {bname} (ID: {batch_id})\n"
        f"⏱ <b>EXTRACTION TIME:</b> {int(minutes):02d}:{int(seconds):02d}\n"
        f"📅 <b>DATE:</b> {local_time.strftime('%d-%m-%Y %H:%M:%S')} IST\n\n"
        f"📊 <b>CONTENT STATS</b>\n"
        f"├─ 📁 Total Links: {len(all_urls)}\n"
        f"├─ 🎬 Videos: {video_count}\n"
        f"├─ 📄 PDFs: {pdf_count}\n"
        f"└─ 📦 Others: {len(all_urls) - video_count - pdf_count}\n\n"
        f"🚀 <b>Extracted by:</b> @{(await app.get_me()).username}\n\n"
        f"<code>╾───• {BOT_TEXT} •───╼</code>"
    )

    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.writelines([url + '\n' for url in all_urls])

    await m.reply_document(document=file_path, caption=caption, parse_mode="html")

    try:
        os.remove(file_path)
    except:
        pass
