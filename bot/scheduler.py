"""YouTube channel RSS checker for subscriptions."""

import asyncio
import logging
from datetime import datetime, timezone

import feedparser

from bot import database as db
from bot.downloader import extract_video_id, download_video
from bot.uploader import upload_video
from bot.config import CHECK_INTERVAL

logger = logging.getLogger(__name__)


def get_channel_feed(channel_id: str) -> feedparser.FeedParserDict | None:
    """Parse YouTube RSS feed for a channel."""
    # Support both @handle and UC... channel IDs
    if channel_id.startswith("@") or channel_id.startswith("UC"):
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    else:
        # Assume it's a handle
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id=@{channel_id}"

    try:
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            # Try alternative format
            if "@" not in channel_id and not channel_id.startswith("UC"):
                feed_url = f"https://www.youtube.com/feeds/videos.xml?search_query={channel_id}"
                feed = feedparser.parse(feed_url)
        return feed if feed.entries else None
    except Exception as e:
        logger.error("RSS parse error for %s: %s", channel_id, e)
        return None


async def process_subscription(sub: dict) -> int:
    """Check a subscription for new videos and upload them.
    Returns count of newly uploaded videos."""
    channel_id = sub["channel_id"]
    album_id = sub["album_id"]
    quality = sub["quality"]
    sub_id = sub["id"]

    feed = get_channel_feed(channel_id)
    if not feed:
        logger.warning("No feed entries for channel %s", channel_id)
        return 0

    uploaded = 0
    for entry in feed.entries:
        yt_url = entry.get("link", "")
        yt_id = extract_video_id(yt_url)
        if not yt_id:
            continue

        # Skip already processed
        if await db.is_video_processed(yt_id):
            continue

        title = entry.get("title", "Untitled")

        # Check publish time (skip videos older than 7 days)
        published = entry.get("published_parsed")
        if published:
            pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
            age = (datetime.now(tz=timezone.utc) - pub_dt).days
            if age > 7:
                logger.info("Skipping old video: %s (%d days)", title, age)
                # Mark as processed to avoid rechecking
                await db.mark_video_processed(yt_id, sub_id, title, quality, 0, 0)
                continue

        logger.info("New video from %s: %s (%s)", channel_id, title, yt_id)

        # Download
        file_path = await download_video(yt_url, quality)
        if not file_path or file_path == "TOO_LARGE":
            if file_path == "TOO_LARGE":
                logger.warning("Video too large, skipping: %s", title)
                await db.mark_video_processed(yt_id, sub_id, title, quality, 0, 0)
            continue

        # Upload to VK
        result = await upload_video(file_path, title, album_id=album_id)
        from bot.downloader import cleanup_file
        cleanup_file(file_path)

        if result:
            await db.mark_video_processed(
                yt_id, sub_id, title, quality,
                result["video_id"], result["owner_id"]
            )
            uploaded += 1
            logger.info("Uploaded: %s → video-%d_%d", title,
                        result["owner_id"], result["video_id"])
        else:
            logger.error("Failed to upload: %s", title)

    # Update last check time
    await db.update_last_check(sub_id)
    return uploaded


async def scheduler_loop():
    """Main scheduler loop: check all active subscriptions periodically."""
    logger.info("Scheduler started (interval: %ds)", CHECK_INTERVAL)
    while True:
        try:
            subs = await db.list_subscriptions()
            active_subs = [s for s in subs if s["active"]]
            logger.info("Checking %d active subscriptions", len(active_subs))

            for sub in active_subs:
                try:
                    count = await process_subscription(sub)
                    if count > 0:
                        logger.info("Subscription %s (%s): %d new videos",
                                    sub["id"], sub["channel_title"], count)
                except Exception as e:
                    logger.error("Error processing subscription %d: %s",
                                 sub["id"], e, exc_info=True)
                # Small delay between subscriptions to avoid rate limits
                await asyncio.sleep(5)

        except Exception as e:
            logger.error("Scheduler error: %s", e, exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL)
