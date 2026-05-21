"""
PW Free (Physics Wallah without login) extractor module.
Adapted from ApnaEx-main/Extractor/modules/freepw.py
"""
import requests
import os
import re
import json
import asyncio
import time
import zipfile
import logging
from typing import List, Dict, Any
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime
import pytz
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

india_timezone = pytz.timezone('Asia/Kolkata')
THREADPOOL = ThreadPoolExecutor(max_workers=5000)


async def fetch_pwwp_data(session, url, headers=None, params=None, data=None, method='GET'):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with session.request(method, url, headers=headers, params=params, json=data) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
        if attempt < max_retries - 1:
            await asyncio.sleep(90 ** attempt)
        else:
            return None


async def process_pwwp_chapter_content(session, chapter_id, batch_id, subject_id, schedule_id, content_type, headers):
    url = f"https://api.penpencil.co/v1/batches/{batch_id}/subject/{subject_id}/schedule/{schedule_id}/schedule-details"
    data = await fetch_pwwp_data(session, url, headers=headers)
    content = []

    if data and data.get("success") and data.get("data"):
        data_item = data["data"]
        if content_type in ("videos", "DppVideos"):
            video_details = data_item.get('videoDetails', {})
            if video_details:
                name = data_item.get('topic', '')
                videoUrl = video_details.get('videoUrl') or video_details.get('embedCode') or ""
                if videoUrl:
                    content.append(f"{name}:{videoUrl}")
        elif content_type in ("notes", "DppNotes"):
            homework_ids = data_item.get('homeworkIds', [])
            for homework in homework_ids:
                attachment_ids = homework.get('attachmentIds', [])
                name = homework.get('topic', '')
                for attachment in attachment_ids:
                    url = attachment.get('baseUrl', '') + attachment.get('key', '')
                    if url:
                        content.append(f"{name}:{url}")
        return {content_type: content} if content else {}
    return {}


async def fetch_pwwp_all_schedule(session, chapter_id, batch_id, subject_id, content_type, headers):
    all_schedule = []
    page = 1
    while True:
        params = {'tag': chapter_id, 'contentType': content_type, 'page': page}
        url = f"https://api.penpencil.co/v2/batches/{batch_id}/subject/{subject_id}/contents"
        data = await fetch_pwwp_data(session, url, headers=headers, params=params)
        if data and data.get("success") and data.get("data"):
            for item in data["data"]:
                item['content_type'] = content_type
                all_schedule.append(item)
            page += 1
        else:
            break
    return all_schedule


async def process_pwwp_chapters(session, chapter_id, batch_id, subject_id, headers):
    content_types = ['videos', 'notes', 'DppNotes', 'DppVideos']
    all_schedule_tasks = [fetch_pwwp_all_schedule(session, chapter_id, batch_id, subject_id, ct, headers) for ct in content_types]
    all_schedules = await asyncio.gather(*all_schedule_tasks)
    all_schedule = []
    for schedule in all_schedules:
        all_schedule.extend(schedule)

    content_tasks = [
        process_pwwp_chapter_content(session, chapter_id, batch_id, subject_id, item["_id"], item['content_type'], headers)
        for item in all_schedule
    ]
    content_results = await asyncio.gather(*content_tasks)

    combined_content = {}
    for result in content_results:
        if result:
            for ct, cl in result.items():
                combined_content.setdefault(ct, []).extend(cl)
    return combined_content


async def get_pwwp_all_chapters(session, batch_id, subject_id, headers):
    all_chapters = []
    page = 1
    while True:
        url = f"https://api.penpencil.co/v2/batches/{batch_id}/subject/{subject_id}/topics?page={page}"
        data = await fetch_pwwp_data(session, url, headers=headers)
        if data and data.get("data"):
            all_chapters.extend(data["data"])
            page += 1
        else:
            break
    return all_chapters


async def process_pwwp_subject(session, subject, batch_id, batch_name, zipf, json_data, all_subject_urls, headers):
    subject_name = subject.get("subject", "Unknown Subject").replace("/", "-")
    subject_id = subject.get("_id")
    json_data[batch_name][subject_name] = {}
    zipf.writestr(f"{subject_name}/", "")

    chapters = await get_pwwp_all_chapters(session, batch_id, subject_id, headers)

    chapter_tasks = []
    for chapter in chapters:
        chapter_name = chapter.get("name", "Unknown Chapter").replace("/", "-")
        zipf.writestr(f"{subject_name}/{chapter_name}/", "")
        json_data[batch_name][subject_name][chapter_name] = {}
        chapter_tasks.append(process_pwwp_chapters(session, chapter["_id"], batch_id, subject_id, headers))

    chapter_results = await asyncio.gather(*chapter_tasks)

    all_urls = []
    for chapter, chapter_content in zip(chapters, chapter_results):
        chapter_name = chapter.get("name", "Unknown Chapter").replace("/", "-")
        for ct in ['videos', 'notes', 'DppNotes', 'DppVideos']:
            if chapter_content.get(ct):
                content = chapter_content[ct]
                content.reverse()
                content_string = "\n".join(content)
                zipf.writestr(f"{subject_name}/{chapter_name}/{ct}.txt", content_string.encode('utf-8'))
                json_data[batch_name][subject_name][chapter_name][ct] = content
                all_urls.extend(content)
    all_subject_urls[subject_name] = all_urls


def find_pw_old_batch(batch_search):
    try:
        response = requests.get("https://abhiguru143.github.io/AS-MULTIVERSE-PW/batch/batch.json")
        response.raise_for_status()
        data = response.json()
    except:
        return []
    return [b for b in data if batch_search.lower() in b['batch_name'].lower()]


async def get_pwwp_todays_schedule_content_details(session, batch_id, subject_id, schedule_id, headers):
    url = f"https://api.penpencil.co/v1/batches/{batch_id}/subject/{subject_id}/schedule/{schedule_id}/schedule-details"
    data = await fetch_pwwp_data(session, url, headers)
    content = []
    if data and data.get("success") and data.get("data"):
        data_item = data["data"]
        video_details = data_item.get('videoDetails', {})
        if video_details:
            name = data_item.get('topic')
            videoUrl = video_details.get('videoUrl') or video_details.get('embedCode')
            if videoUrl:
                content.append(f"{name}:{videoUrl}\n")

        homework_ids = data_item.get('homeworkIds', [])
        for homework in homework_ids:
            for attachment in homework.get('attachmentIds', []):
                url = attachment.get('baseUrl', '') + attachment.get('key', '')
                if url:
                    content.append(f"{homework.get('topic', '')}:{url}\n")

        dpp = data_item.get('dpp')
        if dpp:
            for homework in dpp.get('homeworkIds', []):
                for attachment in homework.get('attachmentIds', []):
                    url = attachment.get('baseUrl', '') + attachment.get('key', '')
                    if url:
                        content.append(f"{homework.get('topic', '')}:{url}\n")
    return content


async def get_pwwp_all_todays_schedule(session, batch_id, headers):
    url = f"https://api.penpencil.co/v1/batches/{batch_id}/todays-schedule"
    details = await fetch_pwwp_data(session, url, headers)
    all_content = []
    if details and details.get("success") and details.get("data"):
        tasks = []
        for item in details['data']:
            tasks.append(asyncio.create_task(
                get_pwwp_todays_schedule_content_details(session, batch_id, item.get('batchSubjectId'), item.get('_id'), headers)
            ))
        results = await asyncio.gather(*tasks)
        for result in results:
            all_content.extend(result)
    return all_content


async def handle_pwfree_logic(app, m):
    """Main PW Free handler - called from __init__.py callback"""
    join = getattr(Config, 'CHANNEL_ID', '')
    user_id = m.from_user.id if m.from_user else m.chat.id

    editable = await m.reply_text("**Enter Working Access Token\n\nOR\n\nEnter Phone Number**")

    try:
        input1 = await app.listen(chat_id=m.chat.id)
        raw_text1 = input1.text
        await input1.delete()
    except:
        await editable.edit("**Timeout!**")
        return

    headers = {
        'Host': 'api.penpencil.co',
        'client-id': '5eb393ee95fab7468a79d189',
        'client-version': '1910',
        'user-agent': 'Mozilla/5.0 (Linux; Android 12; M2101K6P)',
        'randomid': '72012511-256c-4e1c-b4c7-29d67136af37',
        'client-type': 'WEB',
        'content-type': 'application/json; charset=utf-8',
    }

    connector = aiohttp.TCPConnector(limit=1000)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            if raw_text1.isdigit() and len(raw_text1) == 10:
                phone = raw_text1
                data = {"username": phone, "countryCode": "+91", "organizationId": "5eb393ee95fab7468a79d189"}
                try:
                    async with session.post("https://api.penpencil.co/v1/users/get-otp?smsType=0", json=data, headers=headers) as resp:
                        await resp.read()
                except Exception as e:
                    await editable.edit(f"**Error: {e}**")
                    return

                await editable.edit("**ENTER OTP**")
                try:
                    input2 = await app.listen(chat_id=m.chat.id)
                    otp = input2.text
                    await input2.delete()
                except:
                    await editable.edit("**Timeout!**")
                    return

                payload = {
                    "username": phone, "otp": otp,
                    "client_id": "system-admin", "client_secret": "KjPXuAVfC5xbmgreETNMaL7z",
                    "grant_type": "password", "organizationId": "5eb393ee95fab7468a79d189",
                    "latitude": 0, "longitude": 0
                }
                try:
                    async with session.post("https://api.penpencil.co/v3/oauth/token", json=payload, headers=headers) as resp:
                        access_token = (await resp.json())["data"]["access_token"]
                        await editable.edit(f"<b>PW Login Successful ✅</b>\n\n<pre>{access_token}</pre>")
                        editable = await m.reply_text("**Getting Batches...**")
                except Exception as e:
                    await editable.edit(f"**Error: {e}**")
                    return
            else:
                access_token = raw_text1

            headers['authorization'] = f"Bearer {access_token}"

            try:
                async with session.get("https://api.penpencil.co/v3/batches/all-purchased-batches", headers=headers, params={'mode': '1', 'page': '1'}) as resp:
                    resp.raise_for_status()
                    batches = (await resp.json()).get("data", [])
            except:
                await editable.edit("**Login Failed! TOKEN EXPIRED**")
                return

            await editable.edit("**Enter Batch Name**")
            try:
                input3 = await app.listen(chat_id=m.chat.id)
                batch_search = input3.text
                await input3.delete()
            except:
                await editable.edit("**Timeout!**")
                return

            url = f"https://api.penpencil.co/v3/batches/search?name={batch_search}"
            courses = await fetch_pwwp_data(session, url, headers)
            courses = courses.get("data", {}) if courses else {}

            if courses:
                text = ''
                for cnt, course in enumerate(courses):
                    name = course['name']
                    text += f"{cnt + 1}. ```\n{name}```\n"
                await editable.edit(f"**Send index number\n\n{text}\n\nIf Batch Not Listed Enter - No**")

                try:
                    input4 = await app.listen(chat_id=m.chat.id)
                    raw_text4 = input4.text
                    await input4.delete()
                except:
                    await editable.edit("**Timeout!**")
                    return

                if raw_text4.isdigit() and 1 <= int(raw_text4) <= len(courses):
                    course = courses[int(raw_text4) - 1]
                    selected_batch_id = course['_id']
                    selected_batch_name = course['name']
                    clean_batch_name = selected_batch_name.replace("/", "-").replace("|", "-")
                    clean_file_name = f"{user_id}_{clean_batch_name}"
                elif "No" in raw_text4:
                    courses = find_pw_old_batch(batch_search)
                    if courses:
                        text = ''
                        for cnt, course in enumerate(courses):
                            text += f"{cnt + 1}. ```\n{course['batch_name']}```\n"
                        await editable.edit(f"**Send index number\n\n{text}**")

                        input5 = await app.listen(chat_id=m.chat.id)
                        await input5.delete()
                        if input5.text.isdigit() and 1 <= int(input5.text) <= len(courses):
                            course = courses[int(input5.text) - 1]
                            selected_batch_id = course['batch_id']
                            selected_batch_name = course['batch_name']
                            clean_batch_name = selected_batch_name.replace("/", "-").replace("|", "-")
                            clean_file_name = f"{user_id}_{clean_batch_name}"
                        else:
                            raise Exception("Invalid index")
                else:
                    raise Exception("Invalid index")

                await editable.edit("1.```\nFull Batch```\n2.```\nToday's Class```\n3.```\nKhazana```")

                try:
                    input6 = await app.listen(chat_id=m.chat.id)
                    raw_text6 = input6.text
                    await input6.delete()
                except:
                    await editable.edit("**Timeout!**")
                    return

                await editable.edit(f"**Extracting: {selected_batch_name}...**")
                start_time = time.time()

                if raw_text6 == '1':
                    url = f"https://api.penpencil.co/v3/batches/{selected_batch_id}/details"
                    batch_details = await fetch_pwwp_data(session, url, headers=headers)

                    if batch_details and batch_details.get("success"):
                        subjects = batch_details.get("data", {}).get("subjects", [])
                        json_data = {selected_batch_name: {}}
                        all_subject_urls = {}

                        with zipfile.ZipFile(f"{clean_file_name}.zip", 'w') as zipf:
                            tasks = [process_pwwp_subject(session, s, selected_batch_id, selected_batch_name, zipf, json_data, all_subject_urls, headers) for s in subjects]
                            await asyncio.gather(*tasks)

                        with open(f"{clean_file_name}.json", 'w') as f:
                            json.dump(json_data, f, indent=4)

                        with open(f"{clean_file_name}.txt", 'w', encoding='utf-8') as f:
                            for s in subjects:
                                sn = s.get("subject", "Unknown").replace("/", "-")
                                if sn in all_subject_urls:
                                    f.write('\n'.join(all_subject_urls[sn]) + '\n')
                    else:
                        raise Exception("Error fetching batch details")

                elif raw_text6 == '2':
                    selected_batch_name = "Today's Class"
                    today_schedule = await get_pwwp_all_todays_schedule(session, selected_batch_id, headers)
                    if today_schedule:
                        with open(f"{clean_file_name}.txt", "w", encoding="utf-8") as f:
                            f.writelines(today_schedule)
                    else:
                        raise Exception("No Classes Found Today")

                elif raw_text6 == '3':
                    raise Exception("Khazana: Work In Progress")
                else:
                    raise Exception("Invalid option")

                end_time = time.time()
                rt = end_time - start_time
                mins = int(rt // 60)
                secs = int(rt % 60)
                formatted_time = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

                time_new = datetime.now(india_timezone).strftime("%d-%m-%Y %I:%M %p")
                await editable.delete()

                mention = f'<a href="tg://user?id={user_id}">{user_id}</a>'
                caption = (
                    f"࿇ ══━━{mention}━━══ ࿇\n\n"
                    f"🌀 **Aᴘᴘ Nᴀᴍᴇ** : ᴘʜʏsɪᴄs ᴡᴀʟᴀ (𝗣𝘄)\n"
                    f"============================\n\n"
                    f"🎯 **Bᴀᴛᴄʜ Nᴀᴍᴇ** : `{selected_batch_name}`\n\n"
                    f"🌐 **Jᴏɪɴ Us** : {join}\n"
                    f"⌛ **Tɪᴍᴇ Tᴀᴋᴇɴ** : {formatted_time}\n\n"
                    f"❄️ **Dᴀᴛᴇ** : {time_new}"
                )

                files = [f"{clean_file_name}.{ext}" for ext in ["txt", "zip", "json"]]
                for file in files:
                    ext = os.path.splitext(file)[1][1:]
                    try:
                        with open(file, 'rb') as f:
                            await m.reply_document(document=f, caption=caption, file_name=f"{clean_batch_name}.{ext}")
                    except FileNotFoundError:
                        pass
                    except Exception as e:
                        logger.error(f"Error sending {file}: {e}")
                    finally:
                        try:
                            os.remove(file)
                        except:
                            pass
            else:
                raise Exception("No batches found")

        except Exception as e:
            logger.error(f"PW Free error: {e}")
            try:
                await editable.edit(f"**Error: {e}**")
            except:
                pass
