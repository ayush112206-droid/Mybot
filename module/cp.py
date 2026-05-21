"""
ClassPlus (CP) extractor module.
Adapted from ApnaEx-main/Extractor/modules/classplus.py
"""
import requests
import json
import random
import uuid
import time
import asyncio
import io
import aiohttp
from pyrogram import Client, filters
import os
import cloudscraper
import concurrent.futures
import re
from config import Config
from datetime import datetime
import pytz
import base64
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)

india_timezone = pytz.timezone('Asia/Kolkata')

apiurl = "https://api.classplusapp.com"
s = cloudscraper.create_scraper()


async def handle_cp_logic(app, message):
    """Main ClassPlus handler - called from __init__.py callback"""
    await classplus_txt(app, message)


async def classplus_txt(app, message):
    BOT_TEXT = getattr(Config, 'BOT_TEXT', 'Master Extractor')
    current_time = datetime.now(india_timezone)
    time_new = current_time.strftime("%d-%m-%Y %I:%M %p")

    # Step 1: Ask for details
    details = await app.ask(message.chat.id,
        "🔹 <b>CLASSPLUS EXTRACTOR</b> 🔹\n\n"
        "Send **ID & Password** in this format:\n"
        "<code>ORG_CODE*Mobile</code>\n\n"
        "Example:\n"
        "- <code>ABCD*9876543210</code>\n"
        "- <code>eyJhbGciOiJIUzI1NiIsInR5cCI6...</code>"
    )
    user_input = details.text.strip()

    if "*" in user_input:
        try:
            org_code, mobile = user_input.split("*")

            device_id = str(uuid.uuid4()).replace('-', '')
            headers = {
                "Accept": "application/json, text/plain, */*",
                "region": "IN",
                "accept-language": "en",
                "Content-Type": "application/json;charset=utf-8",
                "Api-Version": "51",
                "device-id": device_id
            }

            # Step 2: Fetch Organization Details
            org_response = s.get(f"{apiurl}/v2/orgs/{org_code}", headers=headers).json()
            org_id = org_response["data"]["orgId"]
            org_name = org_response["data"]["orgName"]

            # Step 3: Generate OTP
            otp_payload = {
                'countryExt': '91',
                'orgCode': org_name,
                'viaSms': '1',
                'mobile': mobile,
                'orgId': org_id,
                'otpCount': 0
            }

            otp_response = s.post(f"{apiurl}/v2/otp/generate", json=otp_payload, headers=headers)

            if otp_response.status_code == 200:
                otp_data = otp_response.json()
                session_id = otp_data['data']['sessionId']

                # Step 4: Ask for OTP
                user_otp = await app.ask(message.chat.id,
                    "📱 <b>OTP Verification</b>\n\n"
                    "OTP has been sent to your mobile number.\n"
                    "Please enter the OTP to continue.",
                    timeout=300
                )

                if user_otp.text.isdigit():
                    otp = user_otp.text.strip()

                    # Step 5: Verify OTP
                    fingerprint_id = str(uuid.uuid4()).replace('-', '')
                    verify_payload = {
                        "otp": otp,
                        "countryExt": "91",
                        "sessionId": session_id,
                        "orgId": org_id,
                        "fingerprintId": fingerprint_id,
                        "mobile": mobile
                    }

                    verify_response = s.post(f"{apiurl}/v2/users/verify", json=verify_payload, headers=headers)

                    if verify_response.status_code == 200:
                        verify_data = verify_response.json()
                        if verify_data['status'] == 'success':
                            token = verify_data['data']['token']
                            s.headers['x-access-token'] = token
                            await message.reply_text(
                                "✅ <b>Login Successful!</b>\n\n"
                                "🔑 <b>Your Access Token:</b>\n"
                                f"<code>{token}</code>"
                            )

                            headers = {
                                'x-access-token': token,
                                'user-agent': 'Mobile-Android',
                                'app-version': '1.4.65.3',
                                'api-version': '29',
                                'device-id': '39F093FF35F201D9'
                            }
                            response = s.get(f"{apiurl}/v2/courses?tabCategoryId=1", headers=headers)
                            if response.status_code == 200:
                                courses = response.json()["data"]["courses"]
                                s.session_data = {"token": token, "courses": {course["id"]: course["name"] for course in courses}}
                                await fetch_batches(app, message, org_name, BOT_TEXT=BOT_TEXT, time_new=time_new)
                            else:
                                await message.reply("NO BATCH FOUND ")

                    elif verify_response.status_code in (201, 409):
                        email = str(uuid.uuid4()).replace('-', '') + "@gmail.com"
                        register_payload = {
                            "contact": {
                                "email": email,
                                "countryExt": "91",
                                "mobile": mobile
                            },
                            "fingerprintId": fingerprint_id,
                            "name": "name",
                            "orgId": org_id,
                            "orgName": org_name,
                            "otp": otp,
                            "sessionId": session_id,
                            "type": 1,
                            "viaEmail": 0,
                            "viaSms": 1
                        }

                        register_response = s.post(f"{apiurl}/v2/users/register", json=register_payload, headers=headers)

                        if register_response.status_code == 200:
                            register_data = register_response.json()
                            token = register_data['data']['token']
                            s.headers['x-access-token'] = token

                            await message.reply_text(f"<blockquote> Login successful! Your access token:\n\n`{token}` </blockquote>")

                            headers = {
                                'x-access-token': token,
                                'user-agent': 'Mobile-Android',
                                'app-version': '1.4.65.3',
                                'api-version': '29',
                                'device-id': '39F093FF35F201D9'
                            }
                            response = s.get(f"{apiurl}/v2/courses?tabCategoryId=1", headers=headers)
                            if response.status_code == 200:
                                courses = response.json()["data"]["courses"]
                                s.session_data = {"token": token, "courses": {course["id"]: course["name"] for course in courses}}
                                await fetch_batches(app, message, org_name, BOT_TEXT=BOT_TEXT, time_new=time_new)
                            else:
                                await message.reply("NO BATCH FOUND ")
                        else:
                            await message.reply("Wrong OTP or registration failed.")
                    else:
                        await message.reply("Failed to verify OTP. Please try again.")
            else:
                await message.reply("Failed to generate OTP. Please check your details and try again.")

        except Exception as e:
            await message.reply(f"Error: {str(e)}")

    elif len(user_input) > 20:
        # Token-based login
        headers = {
            'x-access-token': user_input,
            'user-agent': 'Mobile-Android',
            'app-version': '1.4.65.3',
            'api-version': '29',
            'device-id': '39F093FF35F201D9'
        }
        response = s.get(f"{apiurl}/v2/courses?tabCategoryId=1", headers=headers)
        if response.status_code == 200:
            courses = response.json()["data"]["courses"]
            s.session_data = {
                "token": user_input,
                "courses": {course["id"]: course["name"] for course in courses}
            }

            org_name = None
            for course in courses:
                shareable_link = course["shareableLink"]
                if "courses.store" in shareable_link:
                    new_data = shareable_link.split('.')[0].split('//')[-1]
                    org_response = s.get(f"{apiurl}/v2/orgs/{new_data}", headers=headers)
                    if org_response.status_code == 200:
                        org_data = org_response.json().get("data", {})
                        org_name = org_data.get("orgName")
                else:
                    org_name = shareable_link.split('//')[1].split('.')[1]

            await fetch_batches(app, message, org_name, BOT_TEXT=BOT_TEXT, time_new=time_new)
        else:
            await message.reply("Invalid token. Please try again.")
    else:
        await message.reply("Invalid input. Please send details in the correct format.")


async def fetch_batches(app, message, org_name, BOT_TEXT="Master Extractor", time_new=""):
    session_data = s.session_data

    if "courses" in session_data:
        courses = session_data["courses"]

        text = "📚 <b>Available Batches</b>\n\n"
        course_list = []
        for idx, (course_id, course_name) in enumerate(courses.items(), start=1):
            text += f"{idx}. <code>{course_name}</code>\n"
            course_list.append((idx, course_id, course_name))

        selected_index = await app.ask(
            message.chat.id,
            f"{text}\n"
            "Send the index number of the batch to download.",
            timeout=180
        )

        if selected_index.text.isdigit():
            selected_idx = int(selected_index.text.strip())

            if 1 <= selected_idx <= len(course_list):
                selected_course_id = course_list[selected_idx - 1][1]
                selected_course_name = course_list[selected_idx - 1][2]

                await app.send_message(
                    message.chat.id,
                    "🔄 <b>Processing Course</b>\n"
                    f"└─ Current: <code>{selected_course_name}</code>"
                )
                await extract_batch(app, message, org_name, selected_course_id, BOT_TEXT=BOT_TEXT, time_new=time_new)
            else:
                await app.send_message(message.chat.id, "❌ Invalid index number.")
        else:
            await app.send_message(message.chat.id, "❌ Please send a valid index number.")
    else:
        await app.send_message(message.chat.id, "❌ No Batches Found.")


async def extract_batch(app, message, org_name, batch_id, BOT_TEXT="Master Extractor", time_new=""):
    session_data = s.session_data

    if "token" in session_data:
        batch_name = session_data["courses"][batch_id]
        headers = {
            'x-access-token': session_data["token"],
            'user-agent': 'Mobile-Android',
            'app-version': '1.4.65.3',
            'api-version': '29',
            'device-id': '39F093FF35F201D9'
        }

        def encode_partial_url(url):
            if not url:
                return ""
            parsed = urlparse(url)
            base_part = f"{parsed.scheme}://{parsed.netloc}"
            path_part = url[len(base_part):]
            encoded_path = base64.b64encode(path_part.encode()).decode()
            return f"{base_part}{encoded_path}"

        async def fetch_live_videos(course_id):
            outputs = []
            async with aiohttp.ClientSession() as session:
                try:
                    url = f"{apiurl}/v2/course/live/list/videos?type=2&entityId={course_id}&limit=9999&offset=0"
                    async with session.get(url, headers=headers) as response:
                        j = await response.json()
                        if "data" in j and "list" in j["data"]:
                            for video in j["data"]["list"]:
                                name = video.get("name", "Unknown Video")
                                video_url = video.get("url", "")
                                content_hash = video.get("contentHashId", "")
                                if video_url:
                                    encoded_url = encode_partial_url(video_url)
                                    outputs.append(f"{name}:\n{encoded_url}\ncontentHashId: {content_hash}\n")
                except Exception as e:
                    logger.error(f"Error fetching live videos: {e}")
            return outputs

        async def process_course_contents(course_id, folder_id=0, folder_path=""):
            result = []
            url = f'{apiurl}/v2/course/content/get?courseId={course_id}&folderId={folder_id}'
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    course_data = await resp.json()
                    course_data = course_data["data"]["courseContent"]

            tasks = []
            for item in course_data:
                content_type = str(item.get("contentType"))
                sub_id = item.get("id")
                sub_name = item.get("name", "Untitled")
                video_url = item.get("url", "")
                content_hash = item.get("contentHashId", "")

                if content_type in ("2", "3"):
                    if video_url:
                        encoded_url = encode_partial_url(video_url)
                        if content_hash:
                            encoded_url += f"*UGxCP_hash={content_hash}\n"
                        full_info = f"{folder_path}{sub_name}: {encoded_url}"
                        result.append(full_info)

                elif content_type == "1":
                    new_folder_path = f"{folder_path}{sub_name} - "
                    tasks.append(process_course_contents(course_id, sub_id, new_folder_path))

            sub_contents = await asyncio.gather(*tasks)
            for sub_content in sub_contents:
                result.extend(sub_content)

            return result

        async def write_to_file(extracted_data):
            invalid_chars = '\t:/+#|@*.'
            clean_name = ''.join(char for char in batch_name if char not in invalid_chars)
            clean_name = clean_name.replace('_', ' ')
            file_path = f"{clean_name}.txt"
            with open(file_path, "w", encoding='utf-8') as file:
                file.write(''.join(extracted_data))
            return file_path

        extracted_data, live_videos = await asyncio.gather(
            process_course_contents(batch_id),
            fetch_live_videos(batch_id)
        )

        extracted_data.extend(live_videos)
        file_path = await write_to_file(extracted_data)

        video_count = sum(1 for line in extracted_data if "Video" in line or ".mp4" in line)
        pdf_count = sum(1 for line in extracted_data if ".pdf" in line)
        total_links = len(extracted_data)
        other_count = total_links - (video_count + pdf_count)

        caption = (
            f"🎓 <b>COURSE EXTRACTED</b> 🎓\n\n"
            f"📱 <b>APP:</b> {org_name}\n"
            f"📚 <b>BATCH:</b> {batch_name}\n"
            f"📅 <b>DATE:</b> {time_new} IST\n\n"
            f"📊 <b>CONTENT STATS</b>\n"
            f"├─ 📁 Total Links: {total_links}\n"
            f"├─ 🎬 Videos: {video_count}\n"
            f"├─ 📄 PDFs: {pdf_count}\n"
            f"└─ 📦 Others: {other_count}\n\n"
            f"🚀 <b>Extracted by</b>: @{(await app.get_me()).username}\n\n"
            f"<code>╾───• {BOT_TEXT} •───╼</code>"
        )

        await app.send_document(message.chat.id, file_path, caption=caption)

        try:
            os.remove(file_path)
        except:
            pass
