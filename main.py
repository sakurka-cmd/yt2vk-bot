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

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/bot.log"),
    ],
)
logger = logging.getLogger(__name__)


def setup_bot():
    """Create and configure the VK bot."""
    from vkbottle import Bot
    from vkbottle.bot.rules import FromMeRule

    bot = Bot(token=VK_TOKEN)
    bot.labeler.message_view.register_middlewares(
        # Ensure peer_id is from our group
    )
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
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    # Handle graceful shutdown
    loop = asyncio.new_event_loop()
    signals = (signal.SIGTERM, signal.SIGINT)

    for sig in signals:
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.ensure_future(_shutdown(s))
        )

    try:
        loop.run_until_complete(main())
    finally:
        loop.close()


async def _shutdown(sig):
    logger.info("Received signal %s, shutting down...", sig.name)
    import asyncio
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task():
            task.cancel()
    await asyncio.sleep(0.5)
