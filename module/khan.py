"""
Khan GS extractor module.
Adapted from ApnaEx-main/Extractor/modules/khan.py
"""
import logging
import os
import requests
import time
import json
import asyncio
import aiohttp
import aiofiles
from datetime import datetime, timedelta
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from config import Config
import zipfile
from io import BytesIO

# Constants
MAX_WORKERS = 5000
MAX_RETRIES = 15
TIMEOUT = 90
UPDATE_INTERVAL = 15
SESSION_TIMEOUT = 200

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Forward to log helper
async def forward_to_log(msg, label=""):
    try:
