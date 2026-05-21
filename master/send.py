"""
Send module - Batch file processing, URL extraction and encryption.
Reconstructed from send.so (master/send.py).
Handles TXT batch file generation, AES URL encryption/decryption,
DRM/non-DRM video detection, and login flows.
"""
import re
import os
import io
import logging
import asyncio
import aiofiles
import pytz
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)
IST = pytz.timezone('Asia/Kolkata')

# AES key and IV for URL encryption/decryption (16 bytes each)
# Found across all workspace projects (appxfree.py, mix.py, freeappx.py, utk.py, etc.)
AES_KEY = b'638udh3829162018'
AES_IV = b'fedcba9876543210'

# UTK-specific key (used by utk.py module)
UTK_KEY = b'%!$!%_$&!%F)&^!^'
UTK_IV = b'#*y*#2yJ*#$wJv*v'

# Regex patterns for URL extraction (from .so string analysis)
DRM_PATTERN = re.compile(r'\.(m3u8|mpd|mp4)', re.IGNORECASE)
DRM_EXTENDED_PATTERN = re.compile(r'\.(videoid|mpd|testbook)', re.IGNORECASE)
URL_PATTERN = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)


def sanitize_bname(name):
    """Sanitize batch name for safe filename use."""
    if not name:
        return "Batch"
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized[:100] if sanitized else "Batch"


def extract_urls(text_content):
    """
    Extract video/document URLs from text content.
    Categorizes URLs into DRM videos, non-DRM videos, and PDFs.
    
    Returns:
        dict with 'drm_videos', 'non_drm_videos', 'pdfs', 'all_urls'
    """
    if not text_content:
        return {'drm_videos': [], 'non_drm_videos': [], 'pdfs': [], 'all_urls': []}
    
    all_urls = URL_PATTERN.findall(text_content)
    drm_videos = []
    non_drm_videos = []
    pdfs = []
    
    for url in all_urls:
        url = url.strip()
        if not url:
            continue
        
        lower_url = url.lower()
        
        # Check for DRM content
        if DRM_EXTENDED_PATTERN.search(url) or '.mpd' in lower_url:
            drm_videos.append(url)
        elif DRM_PATTERN.search(url):
            if '.m3u8' in lower_url or '.mp4' in lower_url:
                non_drm_videos.append(url)
            else:
                drm_videos.append(url)
        elif lower_url.endswith('.pdf'):
            pdfs.append(url)
        else:
            non_drm_videos.append(url)
    
    return {
        'drm_videos': drm_videos,
        'non_drm_videos': non_drm_videos,
        'pdfs': pdfs,
        'all_urls': all_urls
    }


def enc_url(url):
    """
    Encrypt a URL using AES encryption.
    Used for protecting URLs in generated text files.
    """
    try:
        from Cryptodome.Cipher import AES
        from Cryptodome.Util.Padding import pad
        import base64
        
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        padded_data = pad(url.encode('utf-8'), AES.block_size)
        ciphertext = cipher.encrypt(padded_data)
        return base64.b64encode(ciphertext).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encrypting URL: {e}")
        return url


def dec_url(encrypted_url):
    """
    Decrypt an AES-encrypted URL.
    """
    try:
        from Cryptodome.Cipher import AES
        from Cryptodome.Util.Padding import unpad
        import base64
        
        # Handle colon-separated format (enc_data:extra) used by Appx
        if ':' in encrypted_url:
            encrypted_url = encrypted_url.split(':')[0]
        
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        decoded = base64.b64decode(encrypted_url)
        decrypted = cipher.decrypt(decoded)
        plaintext = unpad(decrypted, AES.block_size)
        return plaintext.decode('utf-8')
    except Exception as e:
        logger.error(f"Error decrypting URL: {e}")
        return encrypted_url


def decrypt_link(link):
    """
    Decrypt a single link with error handling.
    Wraps dec_url with additional validation.
    """
    try:
        if not link or not isinstance(link, str):
            return link
        
        decrypted_link = dec_url(link.strip())
        
        # Validate it looks like a URL
        if decrypted_link and decrypted_link.startswith('http'):
            return decrypted_link
        else:
            logger.warning(f"Invalid URL format: {decrypted_link}")
            return link
    except Exception as e:
        logger.error(f"Error decrypting link: {e}")
        return link


def file_name_encr(name):
    """
    Encrypt a file name for safe storage/transmission.
    """
    try:
        from Cryptodome.Cipher import AES
        from Cryptodome.Util.Padding import pad
        import base64
        
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        padded = pad(name.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encrypting file name: {e}")
        return name


async def master_batch_detail(app, m, urls_data, batch_name, thumb=None):
    """
    Generate batch detail TXT file with statistics and send it.
    
    Args:
        app: Pyrogram client
        m: Message object
        urls_data: dict from extract_urls() or list of URL strings
        batch_name: Name of the batch
        thumb: Optional thumbnail URL
    """
    try:
        now = datetime.now(IST)
        start_time = now.strftime("%d-%m-%Y %I:%M:%S %p")
        
        # Handle both dict and list input
        if isinstance(urls_data, dict):
            drm_count = len(urls_data.get('drm_videos', []))
            video_count = len(urls_data.get('non_drm_videos', []))
            pdf_count = len(urls_data.get('pdfs', []))
            all_urls = urls_data.get('all_urls', [])
        elif isinstance(urls_data, list):
            all_urls = urls_data
            drm_count = sum(1 for u in all_urls if DRM_EXTENDED_PATTERN.search(str(u)))
            video_count = sum(1 for u in all_urls if DRM_PATTERN.search(str(u)) and not DRM_EXTENDED_PATTERN.search(str(u)))
            pdf_count = sum(1 for u in all_urls if str(u).lower().endswith('.pdf'))
        else:
            all_urls = []
            drm_count = video_count = pdf_count = 0
        
        total = len(all_urls) if all_urls else (drm_count + video_count + pdf_count)
        
        safe_name = sanitize_bname(batch_name)
        owner = getattr(Config, 'OWNER', 'Admin')
        bot_text = getattr(Config, 'BOT_TEXT', 'Master Extractor')
        thumb_url = thumb or getattr(Config, 'THUMB_URL', '')
        channel_url = getattr(Config, 'CH_URL', '')
        
        # Build batch detail text
        header = f"**======= BATCH DETAILS =======**\n\n"
        header += f" **Batch Name:** `{safe_name}`\n"
        header += f" **Total Links:** `{total}`\n"
        header += f" **DRM Videos:** `{drm_count}`\n"
        header += f" **Non-DRM Videos:** `{video_count}`\n"
        header += f" **PDFs:** `{pdf_count}`\n"
        header += f" **Extract Time:** {start_time}\n"
        header += f"\n**=======Extract By:-({bot_text})=======**\n"
        
        if thumb_url:
            header += f"\nimageUrl {thumb_url}\n"
        
        # Warning footer
        footer = (
            "\n\n<blockquote><b><i>⚠️ Warning: In this text file, all Url have been "
            "successfully dumped, but the Url are encoded with the loader bot. "
            "This text file will not work with other bots.</i></b></blockquote>"
        )
        
        # Generate the content text
        file_content = header
        
        # Add all URLs (encrypted)
        for i, url in enumerate(all_urls, 1):
            url_str = str(url).strip()
            if url_str:
                encrypted = enc_url(url_str)
                file_content += f"\n{i}. {encrypted}"
        
        file_content += footer
        
        # Save as text file
        filename = f"{safe_name}_Batch_details.txt"
        file_path = os.path.join(os.getcwd(), filename)
        
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(file_content)
        
        # Build caption
        caption = (
            f"📄 **{safe_name}**\n\n"
            f"📊 Total: `{total}` links\n"
            f"🎬 DRM: `{drm_count}` | 📹 Non-DRM: `{video_count}` | 📑 PDF: `{pdf_count}`\n"
            f"⏰ {start_time}\n\n"
            f"** TEXT FILE **"
        )
        
        # Send file to user
        try:
            await app.send_document(
                chat_id=m.chat.id,
                document=file_path,
                caption=caption
            )
        except Exception as send_err:
            logger.error(f"Error sending batch file: {send_err}")
            # Try sending as BytesIO
            file_bytes = io.BytesIO(file_content.encode('utf-8'))
            file_bytes.name = filename
            await app.send_document(
                chat_id=m.chat.id,
                document=file_bytes,
                caption=caption
            )
        
        # Cleanup
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        
        return True
        
    except Exception as e:
        logger.error(f"Error in master_batch_detail: {e}")
        await m.reply_text(f"⚠️ Error generating batch file: {e}")
        return False


async def without_login(app, m, txt_content, batch_name="Batch"):
    """
    Process TXT file content without login credentials.
    Extracts URLs, generates batch detail file.
    
    Args:
        app: Pyrogram client
        m: Message object  
        txt_content: Raw text content with URLs
        batch_name: Name for the batch
    """
    try:
        # Extract URLs from content
        urls_data = extract_urls(txt_content)
        total = len(urls_data.get('all_urls', []))
        
        if total == 0:
            await m.reply_text("❌ No URLs found in the text file.")
            return
        
        await m.reply_text(
            f"✅ Found **{total}** links\n"
            f"🎬 DRM: `{len(urls_data['drm_videos'])}` | "
            f"📹 Non-DRM: `{len(urls_data['non_drm_videos'])}` | "
            f"📑 PDF: `{len(urls_data['pdfs'])}`\n\n"
            f"⏳ Generating batch file..."
        )
        
        # Generate batch detail file
        await master_batch_detail(app, m, urls_data, batch_name)
        
    except Exception as e:
        logger.error(f"Error in without_login: {e}")
        await m.reply_text(f"⚠️ Error: {e}")


async def login(app, m, txt_content, batch_name="Batch"):
    """
    Process TXT file content with login credentials.
    Same as without_login but may include auth-protected URLs.
    
    Args:
        app: Pyrogram client
        m: Message object
        txt_content: Raw text content with URLs
        batch_name: Name for the batch
    """
    try:
        urls_data = extract_urls(txt_content)
        total = len(urls_data.get('all_urls', []))
        
        if total == 0:
            await m.reply_text("❌ No URLs found in the text file.")
            return
        
        await m.reply_text(
            f"✅ Found **{total}** links (with login)\n"
            f"🎬 DRM: `{len(urls_data['drm_videos'])}` | "
            f"📹 Non-DRM: `{len(urls_data['non_drm_videos'])}` | "
            f"📑 PDF: `{len(urls_data['pdfs'])}`\n\n"
            f"⏳ Generating batch file..."
        )
        
        await master_batch_detail(app, m, urls_data, batch_name)
        
    except Exception as e:
        logger.error(f"Error in login: {e}")
        await m.reply_text(f"⚠️ Error: {e}")


async def login_free(app, m, txt_content, batch_name="Batch"):
    """
    Process TXT file content in free/without-login mode.
    Variant for free extractor modules.
    
    Args:
        app: Pyrogram client
        m: Message object
        txt_content: Raw text content with URLs
        batch_name: Name for the batch
    """
    try:
        urls_data = extract_urls(txt_content)
        total = len(urls_data.get('all_urls', []))
        
        if total == 0:
            await m.reply_text("❌ No URLs found in the text file.")
            return
        
        await m.reply_text(
            f"✅ Found **{total}** links (free mode)\n"
            f"🎬 DRM: `{len(urls_data['drm_videos'])}` | "
            f"📹 Non-DRM: `{len(urls_data['non_drm_videos'])}` | "
            f"📑 PDF: `{len(urls_data['pdfs'])}`\n\n"
            f"⏳ Generating batch file..."
        )
        
        await master_batch_detail(app, m, urls_data, batch_name)
        
    except Exception as e:
        logger.error(f"Error in login_free: {e}")
        await m.reply_text(f"⚠️ Error: {e}")
