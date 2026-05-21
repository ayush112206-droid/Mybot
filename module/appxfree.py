"""
Appx Free extractor module.
Adapted from ApnaEx-main/Extractor/modules/freeappx.py
"""
import requests
import os
import re
import json
import asyncio
import time
import logging
from typing import List, Dict, Any
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from pyrogram import Client, filters
from pyrogram.types import Message
from base64 import b64decode
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from datetime import datetime
import pytz
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

india_timezone = pytz.timezone('Asia/Kolkata')
THREADPOOL = ThreadPoolExecutor(max_workers=5000)


def appx_decrypt(enc):
    try:
        enc = b64decode(enc.split(':')[0])
        key = '638udh3829162018'.encode('utf-8')
        iv = 'fedcba9876543210'.encode('utf-8')
        if len(enc) == 0:
            return ""
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(enc), AES.block_size)
        return plaintext.decode('utf-8')
    except:
        return ""


async def fetch_appx_html_to_json(session, url, headers=None, data=None):
    try:
        if data:
            async with session.post(url, headers=headers, data=data) as response:
                text = await response.text()
        else:
            async with session.get(url, headers=headers) as response:
                text = await response.text()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{"status":', text, re.DOTALL)
            if match:
                json_str = text[match.start():]
                try:
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
                except:
                    pass
            return None
    except Exception as e:
        logger.error(f"fetch error: {e}")
        return None


async def fetch_appx_video_id_details_v2(session, api, batch_id, video_id, ytFlag, headers, folder_wise_course, user_id):
    try:
        res = await fetch_appx_html_to_json(
            session,
            f"{api}/get/fetchVideoDetailsById?course_id={batch_id}&folder_wise_course={folder_wise_course}&ytflag={ytFlag}&video_id={video_id}",
            headers
        )
        output = []
        if res and res.get('data'):
            data = res['data']
            Title = data.get("Title", "")

            # 1. YouTube video_id
            fl = data.get("video_id", "")
            if fl:
                dfl = appx_decrypt(fl)
                if dfl:
                    output.append(f"{Title}:https://youtu.be/{dfl}\n")

            # 2. Direct download_link (non-DRM video)
            vl = data.get("download_link", "")
            if vl:
                dvl = appx_decrypt(vl)
                if dvl and ".pdf" not in dvl:
                    output.append(f"{Title}:{dvl}\n")
            else:
                # 3. Encrypted/DRM links array
                encrypted_links = data.get("encrypted_links", [])
                if encrypted_links:
                    first_link = encrypted_links[0]
                    a = first_link.get("path")
                    k = first_link.get("key")
                    if a and k:
                        import base64 as b64mod
                        da = appx_decrypt(a)
                        k1 = appx_decrypt(k)
                        try:
                            k2 = b64mod.b64decode(k1).decode('utf-8')
                        except:
                            k2 = k1
                        output.append(f"{Title}:{da}*{k2}\n")
                    elif a:
                        da = appx_decrypt(a)
                        output.append(f"{Title}:{da}\n")
                else:
                    # 4. Fallback: DRM MPD links
                    drm_res = await fetch_appx_html_to_json(
                        session,
                        f"{api}/get/get_mpd_drm_links?videoid={video_id}&folder_wise_course={folder_wise_course}",
                        headers
                    )
                    if drm_res and drm_res.get('data'):
                        drm_data = drm_res['data']
                        if isinstance(drm_data, list) and drm_data and drm_data[0].get("path"):
                            path = appx_decrypt(drm_data[0]["path"])
                            if path:
                                output.append(f"{Title}:{path}\n")

            # PDF extraction
            pdf_link = appx_decrypt(data.get("pdf_link", "")) if data.get("pdf_link") else None
            if pdf_link:
                is_enc = data.get("is_pdf_encrypted", 0)
                pk = data.get("pdf_encryption_key", "")
                if str(is_enc) == "1" and pk:
                    key = appx_decrypt(pk)
                    if key and key != "abcdefg":
                        output.append(f"{Title}:{pdf_link}*{key}\n")
                    else:
                        output.append(f"{Title}:{pdf_link}\n")
                else:
                    output.append(f"{Title}:{pdf_link}\n")

            pdf_link2 = appx_decrypt(data.get("pdf_link2", "")) if data.get("pdf_link2") else None
            if pdf_link2:
                is_enc2 = data.get("is_pdf2_encrypted", 0)
                pk2 = data.get("pdf2_encryption_key", "")
                if str(is_enc2) == "1" and pk2:
                    key = appx_decrypt(pk2)
                    if key and key != "abcdefg":
                        output.append(f"{Title}:{pdf_link2}*{key}\n")
                    else:
                        output.append(f"{Title}:{pdf_link2}\n")
                else:
                    output.append(f"{Title}:{pdf_link2}\n")

        return output
    except Exception as e:
        return [f"Error video {video_id}: {str(e)}\n"]


async def fetch_appx_video_id_details_v3(session, api, batch_id, video_id, ytFlag, headers, user_id):
    try:
        res = await fetch_appx_html_to_json(
            session,
            f"{api}/get/fetchVideoDetailsById?course_id={batch_id}&folder_wise_course=0&ytflag={ytFlag}&video_id={video_id}",
            headers
        )
        output = []
        if res and res.get('data'):
            data = res['data']
            Title = data.get("Title", "")

            drm_res = await fetch_appx_html_to_json(
                session,
                f"{api}/get/get_mpd_drm_links?folder_wise_course=0&videoid={video_id}",
                headers
            )
            if drm_res and drm_res.get('data'):
                drm_data = drm_res['data']
                if isinstance(drm_data, list) and drm_data and drm_data[0].get("path"):
                    path = appx_decrypt(drm_data[0]["path"])
                    if path:
                        output.append(f"{Title}:{path}\n")

            pdf_link = appx_decrypt(data.get("pdf_link", "")) if data.get("pdf_link") else None
            if pdf_link and pdf_link.endswith(".pdf"):
                is_enc = data.get("is_pdf_encrypted", 0)
                if str(is_enc) == "1":
                    key = appx_decrypt(data.get("pdf_encryption_key", ""))
                    output.append(f"{Title}:{pdf_link}*{key}\n" if key else f"{Title}:{pdf_link}\n")
                else:
                    output.append(f"{Title}:{pdf_link}\n")

        return output
    except Exception as e:
        return [f"Error video {video_id}: {str(e)}\n"]


async def fetch_appx_folder_contents_v2(session, api, batch_id, folder_id, headers, folder_wise_course, user_id):
    try:
        res = await fetch_appx_html_to_json(
            session,
            f"{api}/get/folder_contentsv2?course_id={batch_id}&parent_id={folder_id}",
            headers
        )
        tasks = []
        output = []

        if res and "data" in res:
            for item in res["data"]:
                Title = item.get("Title", "")
                video_id = item.get("id")
                ytFlag = item.get("ytFlag", 0)
                material_type = item.get("material_type", "")

                if material_type == "VIDEO" and video_id:
                    tasks.append(fetch_appx_video_id_details_v2(session, api, batch_id, video_id, ytFlag, headers, folder_wise_course, user_id))
                elif material_type in ("PDF", "TEST"):
                    pdf_link = appx_decrypt(item.get("pdf_link", "")) if item.get("pdf_link") else None
                    if pdf_link and pdf_link.endswith(".pdf"):
                        is_enc = item.get("is_pdf_encrypted", 0)
                        if str(is_enc) == "1":
                            key = appx_decrypt(item.get("pdf_encryption_key", ""))
                            output.append(f"{Title} PDF:{pdf_link}*{key}\n" if key else f"{Title} PDF:{pdf_link}\n")
                        else:
                            output.append(f"{Title} PDF:{pdf_link}\n")
                elif material_type == "IMAGE":
                    thumb = item.get("thumbnail")
                    if thumb:
                        output.append(f"{Title} IMAGE:{thumb}\n")
                elif material_type == "FOLDER":
                    folder_results = await fetch_appx_folder_contents_v2(session, api, batch_id, item.get("id"), headers, folder_wise_course, user_id)
                    if folder_results:
                        output.extend(folder_results)

        if tasks:
            results = await asyncio.gather(*tasks)
            for res in results:
                if res:
                    output.extend(res)
        return output
    except Exception as e:
        logger.error(f"Folder error {folder_id}: {e}")
        return []


def find_appx_matching_apis(search_api, appxapis_file="appxapis.json"):
    matched_apis = []
    try:
        with open(appxapis_file, 'r') as f:
            api_data = json.load(f)
    except:
        return matched_apis

    for item in api_data:
        for term in search_api:
            term = term.strip().lower()
            if term in item["name"].lower() or term in item["api"].lower():
                matched_apis.append(item)

    unique = []
    seen = set()
    for item in matched_apis:
        if item["api"] not in seen:
            unique.append(item)
            seen.add(item["api"])
    return unique


async def process_folder_wise_course_0(session, api, batch_id, headers, user_id):
    res = await fetch_appx_html_to_json(session, f"{api}/get/allsubjectfrmlivecourseclass?courseid={batch_id}&start=-1", headers)
    all_outputs = []
    tasks = []
    if res and "data" in res:
        for subject in res["data"]:
            subjectid = subject.get("subjectid")
            res2 = await fetch_appx_html_to_json(session, f"{api}/get/alltopicfrmlivecourseclass?courseid={batch_id}&subjectid={subjectid}&start=-1", headers)
            if res2 and "data" in res2:
                for topic in res2["data"]:
                    topicid = topic.get("topicid")
                    res3 = await fetch_appx_html_to_json(session, f"{api}/get/livecourseclassbycoursesubtopconceptapiv3?topicid={topicid}&start=-1&courseid={batch_id}&subjectid={subjectid}", headers)
                    if res3 and "data" in res3:
                        for item in res3["data"]:
                            Title = item.get("Title", "")
                            video_id = item.get("id")
                            ytFlag = item.get("ytFlag")
                            mt = item.get("material_type", "")

                            if mt in ("PDF", "TEST"):
                                pdf_link = appx_decrypt(item.get("pdf_link", "")) if item.get("pdf_link") else None
                                if pdf_link and pdf_link.endswith(".pdf"):
                                    is_enc = item.get("is_pdf_encrypted", 0)
                                    if str(is_enc) == "1":
                                        key = appx_decrypt(item.get("pdf_encryption_key", ""))
                                        all_outputs.append(f"{Title}:{pdf_link}*{key}\n" if key else f"{Title}:{pdf_link}\n")
                                    else:
                                        all_outputs.append(f"{Title}:{pdf_link}\n")
                            elif mt == "IMAGE":
                                thumb = item.get("thumbnail")
                                if thumb:
                                    all_outputs.append(f"{Title}:{thumb}\n")
                            elif mt == "VIDEO" and video_id and ytFlag is not None:
                                tasks.append(fetch_appx_video_id_details_v3(session, api, batch_id, video_id, ytFlag, headers, user_id))

    if tasks:
        results = await asyncio.gather(*tasks)
        for res in results:
            all_outputs.extend(res)
    return all_outputs


async def process_folder_wise_course_1(session, api, batch_id, headers, user_id):
    res = await fetch_appx_html_to_json(session, f"{api}/get/folder_contentsv2?course_id={batch_id}&parent_id=-1", headers)
    all_outputs = []
    tasks = []
    if res and "data" in res:
        for item in res["data"]:
            Title = item.get("Title", "")
            video_id = item.get("id")
            ytFlag = item.get("ytFlag")
            mt = item.get("material_type", "")

            if mt in ("PDF", "TEST"):
                pdf_link = appx_decrypt(item.get("pdf_link", "")) if item.get("pdf_link") else None
                if pdf_link and pdf_link.endswith(".pdf"):
                    is_enc = item.get("is_pdf_encrypted", 0)
                    if str(is_enc) == "1":
                        key = appx_decrypt(item.get("pdf_encryption_key", ""))
                        all_outputs.append(f"{Title}:{pdf_link}*{key}\n" if key else f"{Title}:{pdf_link}\n")
                    else:
                        all_outputs.append(f"{Title}:{pdf_link}\n")
            elif mt == "IMAGE":
                thumb = item.get("thumbnail")
                if thumb:
                    all_outputs.append(f"{Title}:{thumb}\n")
            elif mt == "VIDEO":
                tasks.append(fetch_appx_video_id_details_v2(session, api, batch_id, video_id, ytFlag, headers, 1, user_id))
            elif mt == "FOLDER":
                tasks.append(fetch_appx_folder_contents_v2(session, api, batch_id, item.get("id"), headers, 1, user_id))

    if tasks:
        results = await asyncio.gather(*tasks)
        for res in results:
            all_outputs.extend(res)
    return all_outputs


async def handle_appxfree_logic(app, m, app_name=None, api_url=None):
    """Main Appx Free handler - called from __init__.py callback.
    If app_name and api_url are provided (from menu selection), skip the search step.
    Otherwise ask user for app name / API."""
    BOT_TEXT = getattr(Config, 'BOT_TEXT', 'Master Extractor')
    user_id = m.from_user.id if m.from_user else m.chat.id

    connector = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=connector) as session:
        editable = None
        try:
            # If app_name and api_url are pre-resolved from callback, skip search
            if app_name and api_url:
                api = api_url if api_url.startswith("http") else f"https://{api_url}"
                api = api.rstrip("/")
                selected_app_name = app_name
                editable = await m.reply_text(f"📱 Extracting <b>{selected_app_name}</b>...")
            else:
                editable = await m.reply_text("Enter App Name Or Api")

                input1 = await app.listen(chat_id=m.chat.id)
                api_input = input1.text
                await input1.delete()

                if not (api_input.startswith("http://") or api_input.startswith("https://")):
                    search_api = [term.strip() for term in api_input.split()]
                    matches = find_appx_matching_apis(search_api)

                    if matches:
                        text = ''
                        for cnt, item in enumerate(matches):
                            name = item['name']
                            api = item["api"]
                            text += f"{cnt + 1}. {name}:{api}\n"

                        await editable.edit(f"Send index number of the Batch to download.\n\n{text}")

                        input2 = await app.listen(chat_id=m.chat.id)
                        raw_text2 = input2.text
                        await input2.delete()

                        if raw_text2.isdigit() and 1 <= int(raw_text2) <= len(matches):
                            item = matches[int(raw_text2) - 1]
                            api = item['api']
                            selected_app_name = item['name']
                        else:
                            await editable.edit("Error: Wrong Index Number")
                            return
                    else:
                        await editable.edit("No matches found. Enter Correct App Name")
                        return
                else:
                    api = "https://" + api_input.replace("https://", "").replace("http://", "").rstrip("/")
                    selected_app_name = api

            token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjEwMTU1NTYyIiwiZW1haWwiOiJhbm9ueW1vdXNAZ21haWwuY29tIiwidGltZXN0YW1wIjoxNzQ1MDc5MzgyLCJ0ZW5hbnRUeXBlIjoidXNlciIsInRlbmFudE5hbWUiOiIiLCJ0ZW5hbnRJZCI6IiIsImRpc3Bvc2FibGUiOmZhbHNlfQ.EfwLhNtbzUVs1qRkMqc3P6ObkKSO0VYWKdAe6GmhdAg"
            userid = "10155562"

            headers = {
                'User-Agent': "okhttp/4.9.1",
                'Accept-Encoding': "gzip",
                'client-service': "Appx",
                'auth-key': "appxapi",
                'user_app_category': "",
                'language': "en",
                'device_type': "ANDROID"
            }

            await editable.edit("Fetching courses list...")

            res1 = await fetch_appx_html_to_json(session, f"{api}/get/courselist", headers)
            res2 = await fetch_appx_html_to_json(session, f"{api}/get/courselistnewv2", headers)

            courses1 = res1.get("data", []) if res1 and res1.get('status') == 200 else []
            courses2 = res2.get("data", []) if res2 and res2.get('status') == 200 else []
            courses = courses1 + courses2

            if courses:
                text = ''
                for cnt, course in enumerate(courses):
                    name = course.get("course_name", "")
                    price = course.get("price", "N/A")
                    text += f"{cnt + 1}. {name} - Rs.{price}\n"

                if len(courses) > 50:
                    fname = f"{user_id}_paid_course_details.txt"
                    with open(fname, 'w', encoding='utf-8') as f:
                        f.write(text)
                    await editable.delete()
                    msg = await m.reply_document(document=fname, caption=f"📚 {len(courses)} courses found. Send index number.")
                    try:
                        os.remove(fname)
                    except:
                        pass
                    input5 = await app.listen(chat_id=m.chat.id)
                    raw_text5 = input5.text
                    await input5.delete()
                else:
                    await editable.edit(f"📚 <b>Available Courses</b>\n\n{text}\n\nSend index number.")
                    input5 = await app.listen(chat_id=m.chat.id)
                    raw_text5 = input5.text
                    await input5.delete()

                if raw_text5.isdigit() and 1 <= int(raw_text5) <= len(courses):
                    course = courses[int(raw_text5) - 1]
                    selected_batch_id = course['id']
                    selected_batch_name = course['course_name']
                    folder_wise_course = course.get("folder_wise_course", "")
                    clean_batch_name = selected_batch_name.replace('/', '-').replace('|', '-')[:244]
                    clean_file_name = f"{user_id}_{clean_batch_name}"
                else:
                    await editable.edit("❌ Invalid index number!")
                    return

                status_msg = await m.reply_text(f"🔄 Processing: <code>{selected_batch_name}</code>")
                start_time = time.time()

                headers = {
                    "Client-Service": "Appx",
                    "Auth-Key": "appxapi",
                    "source": "website",
                    "Authorization": token,
                    "User-ID": userid
                }

                all_outputs = []
                if folder_wise_course == 0:
                    all_outputs = await process_folder_wise_course_0(session, api, selected_batch_id, headers, user_id)
                elif folder_wise_course == 1:
                    all_outputs = await process_folder_wise_course_1(session, api, selected_batch_id, headers, user_id)
                else:
                    o0 = await process_folder_wise_course_0(session, api, selected_batch_id, headers, user_id)
                    o1 = await process_folder_wise_course_1(session, api, selected_batch_id, headers, user_id)
                    all_outputs = o0 + o1

                if all_outputs:
                    content = ''.join(all_outputs)
                    with open(f"{clean_file_name}.txt", 'w', encoding='utf-8') as f:
                        f.write(content)

                    end_time = time.time()
                    rt = end_time - start_time
                    mins = int(rt // 60)
                    secs = int(rt % 60)
                    formatted_time = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

                    time_new = datetime.now(india_timezone).strftime("%d-%m-%Y %I:%M %p")
                    total_links = len(all_outputs)

                    caption = (
                        f"🎓 <b>COURSE EXTRACTED</b> 🎓\n\n"
                        f"📱 <b>APP:</b> {selected_app_name}\n"
                        f"📚 <b>BATCH:</b> {selected_batch_name}\n"
                        f"⏱ <b>TIME:</b> {formatted_time}\n"
                        f"📅 <b>DATE:</b> {time_new} IST\n\n"
                        f"📊 <b>STATS</b>\n"
                        f"├─ 📁 Total: {total_links}\n"
                        f"└─ ⏱ {formatted_time}\n\n"
                        f"🚀 <b>By:</b> @{(await app.get_me()).username}\n\n"
                        f"<code>╾───• {BOT_TEXT} •───╼</code>"
                    )

                    try:
                        await status_msg.delete()
                        await m.reply_document(
                            document=f"{clean_file_name}.txt",
                            caption=caption,
                            file_name=f"{clean_batch_name}.txt"
                        )
                    except Exception as e:
                        logger.error(f"Error sending: {e}")
                    finally:
                        try:
                            os.remove(f"{clean_file_name}.txt")
                        except:
                            pass
                else:
                    await status_msg.edit("❌ No content found")
            else:
                await editable.edit("❌ No courses found")

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            if editable:
                try:
                    await editable.edit(error_msg)
                except:
                    await m.reply_text(error_msg)