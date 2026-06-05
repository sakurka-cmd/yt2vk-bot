"""yt2vk-bot — YouTube to VK community video bot."""

import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

load_dotenv()

from bot.config import VK_TOKEN, VK_GROUP_ID, LOG_LEVEL
from bot import database
from bot.handlers import register_handlers
from bot.scheduler import scheduler_loop

# Force DEBUG logging for vkbottle to diagnose LP issues
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/bot.log"),
    ],
)
logger = logging.getLogger(__name__)

# Patch vkbottle to add version parameter for new VK LP format
import vkbottle.polling.bot_polling as bp
from aiohttp import ClientTimeout

_orig_get_event = bp.BotPolling.get_event

async def patched_get_event(self, server):
    logger.debug("LP request to %s ts=%s wait=%s", server.get("server"), server.get("ts"), self.wait)
    try:
        result = await self.api.http_client.request_json(
            url=server["server"],
            method="POST",
            params={
                "act": "a_check",
                "key": server["key"],
                "ts": server["ts"],
                "wait": self.wait,
                "version": 3,
            },
            timeout=ClientTimeout(total=self.wait + 10),
        )
        logger.debug("LP response: %s", str(result)[:200])
        return result
    except Exception as e:
        logger.error("LP request failed: %s", e)
        raise

bp.BotPolling.get_event = patched_get_event
logger.info("vkbottle LP patched: added version=3 parameter")


def setup_bot():
    """Create and configure the VK bot."""
    from vkbottle import Bot
    bot = Bot(token=VK_TOKEN)
    return bot


async def main():
    logger.info("Starting yt2vk-bot (VK Group: %s)", VK_GROUP_ID)

    # Initialize database
    await database.init_db()
    logger.info("Database initialized")

    # Setup bot
    bot = setup_bot()
    register_handlers(bot)
    logger.info("Handlers registered")

    # Start scheduler in background
    scheduler_task = asyncio.create_task(scheduler_loop())

    # Run bot polling
    logger.info("Starting VK Long Poll...")
    try:
        await bot.run_polling()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
    finally:
        scheduler_task.cancel()
        await database.close_db()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    loop = asyncio.new_event_loop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.ensure_future(_shutdown(s))
        )

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()


async def _shutdown(sig):
    logger.info("Received signal %s, shutting down...", sig.name)
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task():
            task.cancel()
    await asyncio.sleep(0.5)

