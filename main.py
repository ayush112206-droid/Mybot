"""
Master Extractor Bot - Entry Point
"""
import asyncio
import logging
from config import Config
from pyrogram import Client, idle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
LOGGER = logging.getLogger(__name__)


async def main():
    plugins = dict(root="plugins")
    bot = Client(
        "Master",
        bot_token=Config.BOT_TOKEN,
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        sleep_threshold=120,
        plugins=plugins,
        workers=100,
    )
    async with bot:
        bot_info = await bot.get_me()
        LOGGER.info(f"✅ @{bot_info.username} Started Successfully!")
        await idle()
    LOGGER.info("❌ Bot Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
