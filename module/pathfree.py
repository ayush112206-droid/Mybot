"""
My Pathshala free extractor module.
Adapted from ApnaEx-main/Extractor/modules/mypathshala.py
"""
import asyncio
import aiohttp
import json
import os
import logging
from pyrogram import Client
from pyrogram.types import Message
from datetime import datetime
import pytz
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_pathfree_logic(app, m):
    """Main My Pathshala handler - called from __init__.py callback"""
    BOT_TEXT = getattr(Config, 'BOT_TEXT', 'Master Extractor')

    try:
        start_time = datetime.now()

        editable = await m.reply_text(
            "🔹 <b>MY PATHSHALA EXTRACTOR PRO</b> 🔹\n\n"
            "Send login details in this format:\n"
            "1️⃣ <b>ID*Password:</b> <code>ID*Password</code>\n"
            "2️⃣ <b>Token:</b> <code>your_token</code>\n\n"
            "<i>Example:</i>\n"
            "- ID*Pass: <code>user@mail.com*pass123</code>\n"
            "- Token: <code>eyJhbGciOiJ...</code>"
        )

        input1 = await app.listen(chat_id=m.chat.id)
        raw_text = input1.text.strip()
        await input1.delete()

        try:
            if '*' in raw_text:
                username, password = raw_text.split("*", 1)
                url = 'https://usvc.my-pathshala.com/api/signin'
                headers = {
                    'Host': 'usvc.my-pathshala.com',
                    'Preference': '',
                    'Filter': '1',
                    'Clientid': '2702',
                    'Edustore': 'false',
                    'Platform': 'android',
                    'Content-Type': 'application/json; charset=UTF-8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'User-Agent': 'okhttp/4.8.0',
                    'Connection': 'close'
                }

                data = {
                    "client_id": 2702,
                    "client_secret": "cCZxFzu57FrejvFVvEDmytSfDVaVTjC1EA5e1E34",
                    "password": password,
                    "username": username
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=data) as response:
                        response_text = await response.text()
                        L_data = json.loads(response_text)
                        if 'access_token' not in L_data:
                            await editable.edit_text("❌ <b>Login Failed</b>\n\nPlease check your credentials.")
                            return
                        token = L_data['access_token']
            else:
                token = raw_text

            headers_b = {
                'Authorization': f'Bearer {token}',
                'ClientId': '2702',
                'EduStore': 'false',
                'Platform': 'android',
                'Host': 'csvc.my-pathshala.com',
                'Connection': 'Keep-Alive',
                'Accept-Encoding': 'gzip',
                'User-Agent': 'okhttp/4.8.0'
            }

            mybatch_url = "https://csvc.my-pathshala.com/api/enroll/course?page=1&perPageCount=10"

            async with aiohttp.ClientSession() as session:
                async with session.get(mybatch_url, headers=headers_b) as response:
                    if response.status != 200:
                        await editable.edit_text("❌ <b>Failed to fetch courses</b>")
                        return

                    response_text = await response.text()
                    data = json.loads(response_text).get('response', {}).get('data', [])

                    if not data:
                        await editable.edit_text("❌ <b>No Batches Found</b>")
                        return

                    batch_text = ""
                    for cdata in data:
                        cid = cdata['course']['id']
                        cname = cdata['course']['course_name']
                        batch_text += f"<code>{cid}</code> - <b>{cname}</b> 💰\n\n"

                    await editable.edit_text(
                        f"✅ <b>Login Successful!</b>\n\n"
                        f"📚 <b>Available Batches:</b>\n\n{batch_text}"
                    )

                    for cdata in data:
                        try:
                            cid = cdata['course']['id']
                            cname = cdata['course']['course_name']

                            progress_msg = await m.reply_text(
                                "🔄 <b>Processing</b>\n"
                                f"└─ Current: <code>{cname}</code>"
                            )

                            all_urls = []

                            videos = cdata['course'].get('videos', [])
                            for video in videos:
                                title = video.get('title', '')
                                link = f"https://www.youtube.com/watch?v={video.get('video', '')}"
                                all_urls.append(f"{title}:{link}")

                            assignments = cdata['course'].get('assignments', [])
                            for pdf in assignments:
                                title = pdf.get('assignment_name', '')
                                link = f"https://mps.sgp1.digitaloceanspaces.com/prod/docs/courses/{pdf.get('document', '')}"
                                all_urls.append(f"{title}:{link}")

                            if not all_urls:
                                await progress_msg.edit_text("❌ <b>No content found</b>")
                                continue

                            video_count = sum(1 for u in all_urls if 'youtube.com' in u.lower())
                            pdf_count = sum(1 for u in all_urls if '.pdf' in u.lower())

                            file_name = f"MyPathshala_{cname}_{int(start_time.timestamp())}.txt"
                            with open(file_name, 'w', encoding='utf-8') as f:
                                f.write('\n'.join(all_urls))

                            duration = datetime.now() - start_time
                            minutes, seconds = divmod(duration.total_seconds(), 60)

                            caption = (
                                f"🎓 <b>COURSE EXTRACTED</b> 🎓\n\n"
                                f"📱 <b>APP:</b> My Pathshala\n"
                                f"📚 <b>BATCH:</b> {cname} (ID: {cid})\n"
                                f"⏱ <b>TIME:</b> {int(minutes):02d}:{int(seconds):02d}\n"
                                f"📅 <b>DATE:</b> {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%m-%Y %H:%M:%S')} IST\n\n"
                                f"📊 <b>STATS</b>\n"
                                f"├─ 📁 Total: {len(all_urls)}\n"
                                f"├─ 🎬 Videos: {video_count}\n"
                                f"└─ 📄 PDFs: {pdf_count}\n\n"
                                f"🚀 <b>By:</b> @{(await app.get_me()).username}\n\n"
                                f"<code>╾───• {BOT_TEXT} •───╼</code>"
                            )

                            await m.reply_document(document=file_name, caption=caption, parse_mode="html")

                            try:
                                os.remove(file_name)
                            except:
                                pass

                            await progress_msg.edit_text("✅ <b>Done!</b>")

                        except Exception as e:
                            logger.error(f"Batch error {cname}: {e}")
                            await progress_msg.edit_text(f"❌ Error: <code>{str(e)}</code>")

        except Exception as e:
            await editable.edit_text(f"❌ <b>Login Failed</b>\nError: <code>{str(e)}</code>")

    except Exception as e:
        logger.error(f"My Pathshala error: {e}")
        await m.reply_text(f"❌ Error: <code>{str(e)}</code>")
