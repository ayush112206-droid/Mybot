"""
CareerWill (CW) extractor module.
Adapted from ApnaEx-main/Extractor/modules/careerwill.py
"""
import os
import requests
import threading
import asyncio
import cloudscraper
import time
from pyrogram import Client
from pyrogram.types import Message
from config import Config
import datetime
import logging

logger = logging.getLogger(__name__)

requests_scraper = cloudscraper.create_scraper()
ACCOUNT_ID = "6206459123001"
bc_url = f"https://edge.api.brightcove.com/playback/v1/accounts/{ACCOUNT_ID}/videos/"


def download_thumbnail(url):
    try:
        response = requests_scraper.get(url)
        if response.status_code == 200:
            thumb_path = "thumb_temp.jpg"
            with open(thumb_path, "wb") as f:
                f.write(response.content)
            return thumb_path
        return None
    except Exception:
        return None


async def handle_cw_logic(app, message):
    """Main CareerWill handler - called from __init__.py callback"""
    await career_will(app, message)


async def careerdl(app, message, headers, raw_text2, token, raw_text3, prog, name):
    BOT_TEXT = getattr(Config, 'BOT_TEXT', 'Master Extractor')
    THUMB_URL = getattr(Config, 'THUMB_URL', '')

    num_id = raw_text3.split('&')
    result_text = ""
    total_videos = 0
    total_notes = 0
    total_topics = len(num_id)
    current_topic = 0
    start_time = time.time()

    thumb_path = download_thumbnail(THUMB_URL) if THUMB_URL else None

    for id_text in num_id:
        try:
            current_topic += 1
            details_url = f"https://elearn.crwilladmin.com/api/v9/batch-detail/{raw_text2}?topicId={id_text}"
            response = requests_scraper.get(details_url, headers=headers)
            data = response.json()
            classes = data["data"]["class_list"]["classes"]
            classes.reverse()

            topic_url = f"https://elearn.crwilladmin.com/api/v9/batch-topic/{raw_text2}?type=class"
            topic_data = requests_scraper.get(topic_url, headers=headers).json()["data"]
            topics = topic_data["batch_topic"]
            current_topic_name = next((topic["topicName"] for topic in topics if str(topic["id"]) == id_text), "Unknown Topic")

            elapsed_time = time.time() - start_time
            avg_time = elapsed_time / current_topic
            remaining = total_topics - current_topic
            eta = avg_time * remaining
            elapsed_str = f"{int(elapsed_time//60)}m {int(elapsed_time%60)}s"
            eta_str = f"{int(eta//60)}m {int(eta%60)}s"

            try:
                await prog.edit_text(
                    "🔄 <b>Processing Large Batch</b>\n"
                    f"├─ Subject: {current_topic}/{total_topics}\n"
                    f"├─ Name: <code>{current_topic_name}</code>\n"
                    f"├─ Links: {total_videos + total_notes}\n"
                    f"├─ Time: {elapsed_str}\n"
                    f"└─ ETA: {eta_str}"
                )
            except:
                pass

            for video_data in classes:
                vid_id = video_data['id']
                lesson_name = video_data['lessonName']
                lesson_ext = video_data['lessonExt']

                detail_url = f"https://elearn.crwilladmin.com/api/v9/class-detail/{vid_id}"
                lesson_url = requests_scraper.get(detail_url, headers=headers).json()['data']['class_detail']['lessonUrl']

                if lesson_ext == 'brightcove':
                    video_link = f"{bc_url}{lesson_url}/master.m3u8?bcov_auth={token}"
                    total_videos += 1
                elif lesson_ext == 'youtube':
                    video_link = f"https://www.youtube.com/embed/{lesson_url}"
                    total_videos += 1
                else:
                    continue

                result_text += f"{lesson_name}: {video_link}\n"

            notes_url = f"https://elearn.crwilladmin.com/api/v9/batch-topic/{raw_text2}?type=notes"
            notes_resp = requests_scraper.get(notes_url, headers=headers).json()
            if 'data' in notes_resp and 'batch_topic' in notes_resp['data']:
                for topic in notes_resp['data']['batch_topic']:
                    topic_id = topic['id']
                    notes_topic_url = f"https://elearn.crwilladmin.com/api/v9/batch-notes/{raw_text2}?topicId={topic_id}"
                    notes_data = requests_scraper.get(notes_topic_url, headers=headers).json()
                    for note in reversed(notes_data.get('data', {}).get('notesDetails', [])):
                        doc_title = note.get('docTitle', '')
                        doc_url = note.get('docUrl', '').replace(' ', '%20')
                        line = f"{doc_title}: {doc_url}\n"
                        if line not in result_text:
                            result_text += line
                            total_notes += 1

        except Exception as e:
            await message.reply(f"❌ Error extracting topic: <code>{str(e)}</code>")

    file_name = f"{name.replace('/', '')}.txt"
    with open(file_name, 'w', encoding='utf-8') as f:
        f.write(result_text)

    current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    caption = (
        "🎓 <b>COURSE EXTRACTED</b> 🎓\n\n"
        "📱 <b>APP:</b> CareerWill\n"
        f"📚 <b>BATCH:</b> {name}\n"
        f"📅 <b>DATE:</b> {current_date} IST\n\n"
        "📊 <b>CONTENT STATS</b>\n"
        f"├─ 🎬 Videos: {total_videos}\n"
        f"├─ 📄 PDFs/Notes: {total_notes}\n"
        f"└─ 📦 Total Links: {total_videos + total_notes}\n\n"
        f"🚀 <b>Extracted by:</b> @{(await app.get_me()).username}\n\n"
        f"<code>╾───• {BOT_TEXT} •───╼</code>"
    )

    try:
        await app.send_document(
            message.chat.id, document=file_name, caption=caption,
            thumb=thumb_path if thumb_path else None
        )
