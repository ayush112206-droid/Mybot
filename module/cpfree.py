"""
ClassPlus Free (without login) extractor module.
Adapted from ApnaEx-main/Extractor/modules/freecp.py
"""
import requests
import os
import re
import json
import asyncio
import time
import logging
from typing import List, Dict, Tuple, Any
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


async def download_thumbnail(session, url):
    try:
        thumb_path = f"thumb_{int(time.time())}.jpg"
        async with session.get(url, timeout=30) as response:
            if response.status == 200:
                with open(thumb_path, "wb") as f:
                    f.write(await response.read())
                return thumb_path
    except Exception as e:
        logger.error(f"Thumb error: {e}")
    return None


async def fetch_cpwp_signed_url(url_val, name, session, headers):
    MAX_RETRIES = 5
    for attempt in range(MAX_RETRIES):
        params = {"url": url_val}
        try:
            async with session.get("https://api.classplusapp.com/cams/uploader/video/jw-signed-url", params=params, headers=headers, timeout=60) as response:
                if response.status == 429:
                    await asyncio.sleep(min(2 ** attempt, 30))
                    continue
                response.raise_for_status()
                rj = await response.json()
                signed_url = rj.get("url") or rj.get('drmUrls', {}).get('manifestUrl')
                if signed_url:
                    return signed_url
        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(min(2 ** attempt, 30))
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(min(2 ** attempt, 30))
    return None


async def process_cpwp_url(url_val, name, session, headers):
    try:
        return f"{name}:{url_val}\n"
    except:
        return None


async def get_cpwp_course_content(session, headers, Batch_Token, folder_id=0, limit=9999999999, retry_count=0):
    MAX_RETRIES = 5
    TIMEOUT = 120
    fetched_urls = set()
    results = []
    video_count = pdf_count = image_count = 0
    content_tasks = []
    folder_tasks = []

    try:
        content_api = f'https://api.classplusapp.com/v2/course/preview/content/list/{Batch_Token}'
        params = {'folderId': folder_id, 'limit': limit}

        async with session.get(content_api, params=params, headers=headers, timeout=TIMEOUT) as res:
            if res.status == 429:
                await asyncio.sleep(min(2 ** retry_count, 30))
                return await get_cpwp_course_content(session, headers, Batch_Token, folder_id, limit, retry_count + 1)

            res.raise_for_status()
            res_json = await res.json()
            contents = res_json.get('data', [])

            chunk_size = 5
            for i in range(0, len(contents), chunk_size):
                chunk = contents[i:i + chunk_size]
                for content in chunk:
                    if content.get('contentType') == 1:  # Folder
                        folder_task = asyncio.create_task(get_cpwp_course_content(session, headers, Batch_Token, content['id'], retry_count=0))
                        folder_tasks.append((content['id'], folder_task))
                    else:
                        name = content.get('name', '')
                        url_val = content.get('url') or content.get('thumbnailUrl')
                        if not url_val:
                            continue

                        # Transform CDN URLs to m3u8 streams
                        if "media-cdn.classplusapp.com/tencent/" in url_val:
                            url_val = url_val.rsplit('/', 1)[0] + "/master.m3u8"
                        elif "media-cdn.classplusapp.com" in url_val and url_val.endswith('.jpg'):
                            identifier = url_val.split('/')[-3]
                            url_val = f'https://media-cdn.classplusapp.com/alisg-cdn-a.classplusapp.com/{identifier}/master.m3u8'
                        elif "tencdn.classplusapp.com" in url_val and url_val.endswith('.jpg'):
                            identifier = url_val.split('/')[-2]
                            url_val = f'https://media-cdn.classplusapp.com/tencent/{identifier}/master.m3u8'
                        elif "4b06bf8d61c41f8310af9b2624459378203740932b456b07fcf817b737fbae27" in url_val and url_val.endswith('.jpeg'):
                            video_id = url_val.split('/')[-1].split('.')[0]
                            url_val = f'https://media-cdn.classplusapp.com/alisg-cdn-a.classplusapp.com/b08bad9ff8d969639b2e43d5769342cc62b510c4345d2f7f153bec53be84fe35/{video_id}/master.m3u8'
                        elif "cpvideocdn.testbook.com" in url_val and url_val.endswith('.png'):
                            match = re.search(r'/streams/([a-f0-9]{24})/', url_val)
                            video_id = match.group(1) if match else url_val.split('/')[-2]
                            url_val = f'https://cpvod.testbook.com/{video_id}/playlist.m3u8'
                        elif "media-cdn.classplusapp.com/drm/" in url_val and url_val.endswith('.png'):
                            video_id = url_val.split('/')[-3]
                            url_val = f'https://media-cdn.classplusapp.com/drm/{video_id}/playlist.m3u8'
                        elif "https://media-cdn.classplusapp.com" in url_val and any(x in url_val for x in ["cc/", "lc/", "uc/", "dy/"]) and url_val.endswith('.png'):
                            url_val = url_val.replace('thumbnail.png', 'master.m3u8')
                        elif "https://tb-video.classplusapp.com" in url_val and url_val.endswith('.jpg'):
                            video_id = url_val.split('/')[-1].split('.')[0]
                            url_val = f'https://tb-video.classplusapp.com/{video_id}/master.m3u8'

                        if url_val.endswith(("master.m3u8", "playlist.m3u8")) and url_val not in fetched_urls:
                            fetched_urls.add(url_val)
                            headers2 = {'x-access-token': 'eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9'}
                            task = asyncio.create_task(process_cpwp_url(url_val, name, session, headers2))
                            content_tasks.append((content['id'], task))
                            video_count += 1
                        else:
                            if url_val:
                                fetched_urls.add(url_val)
                                results.append(f"{name}:{url_val}\n")
                                if url_val.endswith('.pdf'):
                                    pdf_count += 1
                                else:
                                    image_count += 1

                await asyncio.sleep(1)

    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(min(2 ** retry_count, 30))
            return await get_cpwp_course_content(session, headers, Batch_Token, folder_id, limit, retry_count + 1)
        return [], 0, 0, 0
    except Exception as e:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(min(2 ** retry_count, 30))
            return await get_cpwp_course_content(session, headers, Batch_Token, folder_id, limit, retry_count + 1)
        return [], 0, 0, 0

    # Process content tasks
    chunk_size = 10
    for i in range(0, len(content_tasks), chunk_size):
        chunk = content_tasks[i:i + chunk_size]
        try:
            chunk_results = await asyncio.wait_for(
                asyncio.gather(*(task for _, task in chunk), return_exceptions=True),
                timeout=TIMEOUT
            )
            for result in chunk_results:
                if isinstance(result, Exception):
                    pass
                elif result:
                    results.append(result)
            await asyncio.sleep(1)
        except asyncio.TimeoutError:
            continue

    # Process folder tasks
    for i in range(0, len(folder_tasks), chunk_size):
        chunk = folder_tasks[i:i + chunk_size]
        try:
            chunk_results = await asyncio.wait_for(
                asyncio.gather(*(task for _, task in chunk), return_exceptions=True),
                timeout=TIMEOUT
            )
            for fid_result in chunk_results:
                if isinstance(fid_result, Exception):
                    pass
                else:
                    nested_results, nvc, npc, nic = fid_result
                    if nested_results:
                        results.extend(nested_results)
                    video_count += nvc
                    pdf_count += npc
                    image_count += nic
            await asyncio.sleep(1)
        except asyncio.TimeoutError:
            continue

    return results, video_count, pdf_count, image_count


async def handle_cpfree_logic(app, m):
    """Main ClassPlus Free handler - called from __init__.py callback"""
    BOT_TEXT = getattr(Config, 'BOT_TEXT', 'Master Extractor')
    join = getattr(Config, 'CHANNEL_ID', '')
    THUMB_URL = getattr(Config, 'THUMB_URL', None)
    user_id = m.from_user.id if m.from_user else m.chat.id

    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-encoding': 'gzip',
        'accept-language': 'EN',
        'api-version': '35',
        'app-version': '1.4.73.2',
        'build-number': '35',
        'connection': 'Keep-Alive',
        'content-type': 'application/json',
        'device-details': 'Xiaomi_Redmi 7_SDK-32',
        'device-id': 'c28d3cb16bbdac01',
        'host': 'api.classplusapp.com',
        'region': 'IN',
        'user-agent': 'Mobile-Android',
        'x-access-token': 'eyJhbGciOiJIUzM4NCIsInR5cCI6IkpXVCJ9.eyJpZCI6MTIyMDc4ODg0LCJvcmdJZCI6NzExNTI4LCJ0eXBlIjoxLCJtb2JpbGUiOiI5MTg2MDAzOTAyODgiLCJuYW1lIjoiU2Fua2V0IFNvbmFyIiwiZW1haWwiOiJoanMuc2Fua2V0QGdtYWlsLmNvbSIsImlzSW50ZXJuYXRpb25hbCI6MCwiZGVmYXVsdExhbmd1YWdlIjoiRU4iLCJjb3VudHJ5Q29kZSI6IklOIiwiY291bnRyeUlTTyI6IjkxIiwidGltZXpvbmUiOiJHTVQrNTozMCIsImlzRGl5Ijp0cnVlLCJvcmdDb2RlIjoidWphbGFmIiwiaXNEaXlTdWJhZG1pbiI6MCwiZmluZ2VycHJpbnRJZCI6IjE3MjAxMDU1NjkwMjYiLCJpYXQiOjE3NDkyNTUzOTUsImV4cCI6MTc0OTg2MDE5NX0.uKdyXfFDtcdyaUItjc_G1ALYwtKxVyuG_SnPhRPa2cNy9Tzd0TaXdXNw1d2cUurv'
    }

    connector = aiohttp.TCPConnector(limit=1000)
    async with aiohttp.ClientSession(connector=connector) as session:
        editable = None
        try:
            user = await app.get_users(user_id)
            user_name = user.first_name
            if user.last_name:
                user_name += f" {user.last_name}"
            mention = f'<a href="tg://user?id={user_id}">{user_name}</a>'

            editable = await m.reply_text("**Enter ORG Code Of Your Classplus App**")

            input1 = await app.listen(chat_id=m.chat.id)
            org_code = input1.text.lower()
            await input1.delete()

            hash_headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0 Safari/537.36'
            }

            async with session.get(f"https://{org_code}.courses.store", headers=hash_headers) as response:
                html_text = await response.text()
                hash_match = re.search(r'"hash":"(.*?)"', html_text)

                if hash_match:
                    token = hash_match.group(1)
                    all_courses = []
                    page = 0
                    page_size = 100

                    try:
                        async with session.get(
                            f"https://api.classplusapp.com/v2/course/search/published?limit={page_size}&offset={page}&sortBy=courseCreationDate&status=published",
                            headers=headers
                        ) as response:
                            if response.status == 200:
                                rj = await response.json()
                                courses = rj.get('data', {}).get('courses', [])
                                if courses:
                                    all_courses.extend(courses)
                            else:
                                while True:
                                    async with session.get(
                                        f"https://api.classplusapp.com/v2/course/preview/similar/{token}?limit={page_size}&page={page}",
                                        headers=headers
                                    ) as resp2:
                                        if resp2.status == 200:
                                            rj = await resp2.json()
                                            courses = rj.get('data', {}).get('coursesData', [])
                                            if not courses:
                                                break
                                            all_courses.extend(courses)
                                            page += 1
                                            if len(courses) < page_size:
                                                break
                                        else:
                                            break

                        if not all_courses:
                            raise Exception("No batches found!")

                        all_courses.sort(key=lambda x: x.get('name', '').lower())

                        text = ''
                        for cnt, course in enumerate(all_courses):
                            name = course.get('name', 'Untitled')
                            price = course.get('finalPrice', 'N/A')
                            text += f"{cnt + 1}. ```\n{name} 💵₹{price}```\n"

                        await editable.edit(f"**Send index number\n\n{text}\n\nFor multiple batches use & separator (e.g. 1&2&3)**")

                        batch_input = await app.listen(chat_id=m.chat.id)
                        raw_text2 = batch_input.text
                        await batch_input.delete()

                    except Exception as e:
                        if editable:
                            try:
                                await editable.edit(f"**Error: {e}**")
                            except:
                                await m.reply_text(f"**Error: {e}**")
                        return
                else:
                    raise Exception("No courses found for this org code")

            # Process batch indices
            batch_indices = raw_text2.split('&')
            total_batches = len(batch_indices)
            processed = 0

            for batch_index in batch_indices:
                batch_index = batch_index.strip()
                start_time = time.time()
                thumb_path = None

                if processed > 0:
                    await asyncio.sleep(5)

                if THUMB_URL:
                    thumb_path = await download_thumbnail(session, THUMB_URL)

                if batch_index.isdigit() and int(batch_index) <= len(all_courses):
                    course = all_courses[int(batch_index) - 1]
                    selected_batch_id = course['id']
                    selected_batch_name = course['name']
                    clean_batch_name = selected_batch_name.replace("/", "-").replace("|", "-")

                    status_msg = await m.reply_text(f"**📥 Extracting {processed+1}/{total_batches}: `{selected_batch_name}`**")

                    batch_headers = {
                        'Accept': 'application/json, text/plain, */*',
                        'region': 'IN',
                        'accept-language': 'EN',
                        'Api-Version': '22',
                        'tutorWebsiteDomain': f'https://{org_code}.courses.store'
                    }

                    try:
                        async with session.get("https://api.classplusapp.com/v2/course/preview/org/info", params={'courseId': str(selected_batch_id)}, headers=batch_headers) as resp:
                            if resp.status == 200:
                                rj = await resp.json()
                                Batch_Token = rj['data']['hash']
                                App_Name = rj['data']['name']

                                course_content, vc, pc, ic = await get_cpwp_course_content(session, headers, Batch_Token)

                                if course_content:
                                    batch_filename = f"{clean_batch_name}_{batch_index}.txt"
                                    content = ''.join(course_content)
                                    with open(batch_filename, 'w', encoding='utf-8') as f:
                                        f.write(content)

                                    end_time = time.time()
                                    rt = end_time - start_time
                                    mins = int(rt // 60)
                                    secs = int(rt % 60)
                                    formatted_time = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                                    time_new = datetime.now(india_timezone).strftime("%d-%m-%Y %I:%M %p")

                                    caption = (
                                        f"࿇ ══━━{mention}━━══ ࿇\n\n"
                                        f"🌀 **Aᴘᴘ Nᴀᴍᴇ** : {App_Name}\n"
                                        f"🔑 **Oʀɢ Cᴏᴅᴇ** : `{org_code}`\n"
                                        f"============================\n\n"
                                        f"🎯 **Bᴀᴛᴄʜ Nᴀᴍᴇ** : `{clean_batch_name}`\n"
                                        f"<blockquote>🎬 : {vc} | 📁 : {pc} | 🖼 : {ic}</blockquote>\n\n"
                                        f"🌐 **Jᴏɪɴ Us** : {join}\n"
                                        f"⌛ **Tɪᴍᴇ Tᴀᴋᴇɴ** : {formatted_time}\n\n"
                                        f"❄️ **Dᴀᴛᴇ** : {time_new}"
                                    )

                                    try:
                                        with open(batch_filename, 'rb') as f:
                                            await m.reply_document(document=f, caption=caption, thumb=thumb_path, file_name=f"{clean_batch_name}.txt")
