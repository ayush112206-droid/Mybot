"""
Server module - HTTP utility functions.
Reconstructed from server.so (master/server.py).
Provides async and sync HTTP request utilities used by all extractor modules.
"""
import aiohttp
import requests
import cloudscraper
import asyncio
import logging
import random
import string
import re
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=4)


async def fetch_aio(url, headers=None):
    """Async GET request returning JSON response."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                return await resp.json(content_type=None)
    except Exception as e:
        logger.error(f"fetch_aio error: {e}")
        return None


async def post_aio(url, data=None, headers=None, json_data=None):
    """Async POST request returning JSON response."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers, json=json_data, 
                                     timeout=aiohttp.ClientTimeout(total=30)) as resp:
                return await resp.json(content_type=None)
    except Exception as e:
        logger.error(f"post_aio error: {e}")
        return None


async def post_data(url, data=None, headers=None, json_data=None):
    """Async POST request returning text response."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers, json=json_data,
                                     timeout=aiohttp.ClientTimeout(total=30)) as resp:
                return await resp.text()
    except Exception as e:
        logger.error(f"post_data error: {e}")
        return None


async def fetch_text(url, headers=None):
    """Async GET request returning text response."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                return await resp.text()
    except Exception as e:
        logger.error(f"fetch_text error: {e}")
        return None


def get_data(url, headers=None, max_retries=3):
    """
    Sync GET request with retry logic and rate limiting.
    Uses ThreadPoolExecutor for blocking calls.
    """
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 429:
                wait_time = int(resp.headers.get('Retry-After', 5))
                logger.warning(f"Rate limit hit. Retrying in {wait_time}s...")
                import time
                time.sleep(wait_time)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            return resp.text
        except Exception as e:
            logger.error(f"get_data attempt {attempt + 1} error: {e}")
            if attempt == max_retries - 1:
                logger.error("Max retries reached. Unable to post data.")
                return None
    return None


def get_random_token(length=32):
    """Generate a random token string."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def sanitize_bname(name):
    """
    Sanitize batch name for use in filenames.
    Removes special characters and trims whitespace.
    """
    if not name:
        return "Batch"
    # Remove characters not safe for filenames
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    # Trim to reasonable length
    return sanitized[:100] if sanitized else "Batch"


def direct_get(url, headers=None):
    """Sync GET request using requests library, returns response object."""
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        return resp
    except Exception as e:
        logger.error(f"direct_get error: {e}")
        return None


def direct_get_json(url, headers=None):
    """Sync GET request returning JSON response."""
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        return resp.json()
    except Exception as e:
        logger.error(f"direct_get_json error: {e}")
        return None


def post_json_body(url, json_body=None, headers=None, max_retries=3):
    """
    Sync POST request with JSON body and retry logic.
    """
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=json_body, headers=headers, timeout=30)
            if resp.status_code == 429:
                wait_time = int(resp.headers.get('Retry-After', 5))
                logger.warning(f"Rate limit hit. Retrying in {wait_time}s...")
                import time
                time.sleep(wait_time)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            return resp.text
        except Exception as e:
            logger.error(f"post_json_body attempt {attempt + 1} error: {e}")
            if attempt == max_retries - 1:
                logger.error("Max retries reached. Unable to post data.")
                return None
    return None


# Cloudscraper-based requests for sites with anti-bot protection
_scraper = None

def _get_scraper():
    """Get or create a cloudscraper instance."""
    global _scraper
    if _scraper is None:
        _scraper = cloudscraper.create_scraper()
    return _scraper


def scraper_get(url, headers=None):
    """GET request using cloudscraper to bypass anti-bot protection."""
    try:
        scraper = _get_scraper()
        resp = scraper.get(url, headers=headers, timeout=30)
        return resp
    except Exception as e:
        logger.error(f"scraper_get error: {e}")
        return None


def scraper_get_json(url, headers=None):
    """GET request using cloudscraper returning JSON."""
    try:
        scraper = _get_scraper()
        resp = scraper.get(url, headers=headers, timeout=30)
        return resp.json()
    except Exception as e:
        logger.error(f"scraper_get_json error: {e}")
        return None
