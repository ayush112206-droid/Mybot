"""
Vision IAS extractor module.
Adapted from ApnaEx-main/Extractor/modules/vision.py
"""
import os
import re
import json
import shutil
import logging
import zipfile
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import requests
from pyrogram.types import Message
from pyrogram import Client
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://www.visionias.in"
TMP_DIR = "tmp_downloads"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
    logger.warning("beautifulsoup4 not installed, Vision IAS extractor will not work")


class VisionIASExtractor:
    def __init__(self, app: Optional[Client] = None, message: Optional[Message] = None):
        self.session = requests.Session()
        self.app = app
        self.message = message
        self.cookies = {}
        self.video_urls = []
        self.pdf_files = []

        if not os.path.exists(TMP_DIR):
            os.makedirs(TMP_DIR)

    async def send_message(self, text: str):
        if self.app and self.message:
            try:
                await self.message.edit_text(text)
            except:
                pass
        else:
            print(text)

    def get_video_url(self, video_page_url: str) -> Optional[str]:
        if not BeautifulSoup:
            return None
        try:
            video_page = self.session.get(
                f"{BASE_URL}/student/pt/video_student/{video_page_url}",
                headers=HEADERS, cookies=self.cookies, verify=False
            ).text
            soup = BeautifulSoup(video_page, 'html.parser')
            iframe = soup.select_one('.js-video iframe')
            if iframe and iframe.get('src'):
                return iframe['src']
        except Exception as e:
            logger.error(f"Error getting video URL: {e}")
        return None

    async def login(self, user_id: str, password: str) -> bool:
        if not BeautifulSoup:
            await self.send_message("❌ beautifulsoup4 not installed!")
            return False
        try:
            login_headers = HEADERS.copy()
            login_headers.update({
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/student/module/login.php"
            })

            payload = {"login": user_id, "password": password, "returnUrl": "student"}

            login_response = self.session.post(
                f"{BASE_URL}/student/module/login-exec2test.php",
                data=payload, headers=login_headers, verify=False
            )

            if "Invalid" in login_response.text:
                await self.send_message("❌ Invalid credentials!")
                return False

            self.cookies = dict(login_response.cookies)
            HEADERS["Cookie"] = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

            batch_response = self.session.get(
                f"{BASE_URL}/student/pt/video_student/live_class_dashboard.php",
                headers=HEADERS, cookies=self.cookies, verify=False
            )

            soup = BeautifulSoup(batch_response.text, 'html.parser')
            course_divs = soup.find_all('div', class_='grid-one-third alpha phn-tab-grid-full phn-tab-mb-30')

            if not course_divs:
                await self.send_message("❌ No batches found!")
                return False

            batch_list = []
            for div in course_divs:
                course_name = div.find('h4').text.strip()
                batch_id = div.find('p', class_='ldg-sectionAvailableCourses_classes')
                if batch_id:
                    batch_id = batch_id.text.strip().replace('(', '').replace(')', '')
                    batch_list.append(f"🔹 `{batch_id}` - {course_name}")

            await self.send_message(
                f"✅ Login Successful!\n👤 User: {user_id}\n\n"
                f"📚 Available Batches:\n\n" + "\n".join(batch_list) +
                "\n\nSend batch ID to start extraction..."
            )
            return True

        except Exception as e:
            await self.send_message(f"❌ Login error: {str(e)}")
            return False

    async def extract_video_urls(self, batch_id: str) -> bool:
        if not BeautifulSoup:
            return False
        try:
            await self.send_message(
                "🔄 <b>Initializing Video Extraction</b>\n└─ Setting up session..."
            )

            current_headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'max-age=0',
                'referer': f'https://visionias.in/student/pt/video_student/video_student_dashboard.php?package_id={batch_id}',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }

            dashboard_response = self.session.get(
                f"{BASE_URL}/student/pt/video_student/video_student_dashboard.php",
                params={'package_id': batch_id},
                headers=current_headers, cookies=self.cookies, verify=False
            )

            video_ids = list(set(re.findall(r'vid=(\d+)', dashboard_response.text)))

            if not video_ids:
                await self.send_message("❌ <b>No Videos Found</b>")
                return False

            await self.send_message(
                f"📊 <b>Package Analysis</b>\n"
                f"├─ Package ID: <code>{batch_id}</code>\n"
                f"├─ Video Sections: <code>{len(video_ids)}</code>\n"
                f"└─ Starting extraction..."
            )

            total_sections = len(video_ids)
            total_videos = 0

            for section_num, vid in enumerate(video_ids, 1):
                try:
                    await self.send_message(
                        f"🎥 <b>Processing Section</b>\n"
                        f"├─ Section: <code>{section_num}/{total_sections}</code>\n"
                        f"└─ Video ID: <code>{vid}</code>"
                    )
                except:
                    pass

                params = {'vid': vid, 'package_id': batch_id}

                try:
                    response = self.session.get(
                        'https://visionias.in/student/pt/video_student/video_class_timeline_dashboard.php',
                        params=params, cookies=self.cookies,
                        headers=current_headers, verify=False
                    )

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "html.parser")
                        all_links = soup.select("ul.gw-submenu a")
                        section_videos = len(all_links)
                        total_videos += section_videos

                        for link in all_links:
                            name = link.get_text(strip=True)
                            url = link.get("href")
                            if url:
                                self.video_urls.append(f"{name}: {url}")
                except Exception as e:
                    logger.error(f"Section error for vid {vid}: {e}")
                    continue

            if self.video_urls:
                with open("classes_links.txt", "w", encoding="utf-8") as f:
                    f.write(f"=== Vision IAS Package {batch_id} Videos ===\n\n")
                    for i, url in enumerate(self.video_urls, 1):
                        f.write(f"{i}. {url}\n")

                await self.send_message(
                    f"✅ <b>Video Extraction Complete</b>\n"
                    f"├─ Total Sections: <code>{total_sections}</code>\n"
                    f"├─ Total Videos: <code>{len(self.video_urls)}</code>\n"
                    f"└─ Saved to: <code>classes_links.txt</code>"
                )
                return True
            else:
                await self.send_message("❌ <b>No Videos Found</b>")
                return False

        except Exception as e:
            await self.send_message(f"❌ <b>Extraction Failed</b>\nError: <code>{str(e)}</code>")
            return False

    async def download_pdfs(self, batch_id: str) -> bool:
        if not BeautifulSoup:
            return False
        try:
            await self.send_message("📑 Fetching PDFs...")

            response = self.session.get(
                f'{BASE_URL}/student/pt/video_student/all_handout.php',
                params={'package_id': batch_id},
                headers=HEADERS, cookies=self.cookies, verify=False
            ).text

            soup = BeautifulSoup(response, 'html.parser')
            li_tags = soup.find_all('li', id='card_type')

            if not li_tags:
                await self.send_message("❌ No PDFs found!")
                return False

            total_pdfs = len(li_tags)
            for i, li in enumerate(li_tags, 1):
                try:
                    title = li.find('div', class_='card-body_custom').text.strip()
                    url = li.find('a')['href']
                    safe_title = "".join(x for x in title if x.isalnum() or x in "._- ")

                    pdf_response = self.session.get(
                        f"{BASE_URL}/student/pt/video_student/{url}",
                        headers=HEADERS, cookies=self.cookies, verify=False, stream=True
                    )

                    if pdf_response.status_code == 200:
                        pdf_path = os.path.join(TMP_DIR, f"{safe_title}.pdf")
                        with open(pdf_path, 'wb') as f:
                            for chunk in pdf_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        self.pdf_files.append(pdf_path)

                except Exception as e:
                    logger.error(f"Error downloading PDF: {e}")
                    continue

            return True

        except Exception as e:
            await self.send_message(f"❌ Error: {str(e)}")
            return False

    def cleanup(self):
        for pdf in self.pdf_files:
            try:
                os.remove(pdf)
            except:
                pass
        try:
            if os.path.exists(TMP_DIR) and not os.listdir(TMP_DIR):
                os.rmdir(TMP_DIR)
        except:
            pass

    async def extract_batch(self, batch_id: str, batch_name: str):
        try:
            start_time = datetime.now()
            await self.send_message(
                f"🚀 <b>Starting Batch Extraction</b>\n"
                f"├─ Batch ID: <code>{batch_id}</code>\n"
                f"└─ Name: <code>{batch_name}</code>"
            )

            videos_extracted = await self.extract_video_urls(batch_id)
            if await self.download_pdfs(batch_id):
                pass  # PDFs handled

            duration = datetime.now() - start_time
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)

            await self.send_message(
                f"✨ <b>Extraction Complete!</b>\n\n"
                f"📊 <b>Results Summary</b>\n"
                f"├─ Videos: <code>{len(self.video_urls)}</code>\n"
                f"├─ PDFs: <code>{len(self.pdf_files)}</code>\n"
                f"└─ Duration: <code>{minutes}m {seconds}s</code>"
            )

        except Exception as e:
            await self.send_message(f"❌ <b>Extraction Failed</b>\nError: <code>{str(e)}</code>")
        finally:
            self.cleanup()

    async def run(self):
        try:
            if self.app and self.message:
                await self.send_message(
                    "🔹 <b>VISION IAS EXTRACTOR</b> 🔹\n\n"
                    "Send login credentials in format: <code>ID*Password</code>\n"
                    "Example: <code>email@gmail.com*password</code>"
                )
                response = await self.app.listen(self.message.chat.id, timeout=300)
                creds = response.text.strip()
            else:
                creds = input("Enter ID*Password: ")

            user_id, password = creds.split('*', 1)

            if not await self.login(user_id.strip(), password.strip()):
                return

            if self.app and self.message:
                response = await self.app.listen(self.message.chat.id, timeout=300)
                batch_id = response.text.strip()
            else:
                batch_id = input("Enter batch ID: ")

            await self.extract_batch(batch_id, f"Batch_{batch_id}")

        except Exception as e:
            await self.send_message(f"❌ Error: {str(e)}")
        finally:
            self.cleanup()
            try:
                self.session.get(f'{BASE_URL}/student/logout.php', headers=HEADERS)
            except:
                pass


async def handle_vision_logic(app, message):
    """Main Vision IAS handler - called from __init__.py callback"""
    editable = await message.reply_text("🔄 Initializing Vision IAS Extractor...")
    extractor = VisionIASExtractor(app, editable)
    await extractor.run()
