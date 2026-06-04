"""VK Video upload via API."""

import asyncio
import logging
import os

import aiohttp

from bot.config import VK_TOKEN, VK_GROUP_ID

logger = logging.getLogger(__name__)

VK_API = "https://api.vk.com/method"


async def vk_request(method: str, params: dict | None = None) -> dict:
    """Make a VK API request."""
    params = params or {}
    params.setdefault("access_token", VK_TOKEN)
    params.setdefault("v", "5.131")
    params.setdefault("group_id", VK_GROUP_ID)

    url = f"{VK_API}/{method}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=params) as resp:
            data = await resp.json(content_type=None)
            if "error" in data:
                logger.error("VK API error %s: %s", method, data["error"])
            return data


async def create_album(title: str, description: str = "",
                       privacy: int = 0) -> dict | None:
    """Create a video album in the community. Returns album dict or None."""
    result = await vk_request("video.addAlbum", {
        "title": title,
        "description": description,
        "privacy": privacy,
    })
    if "response" in result:
        album_id = result["response"]["album_id"]
        logger.info("Created album: %s (id=%d)", title, album_id)
        return {"album_id": album_id, **result["response"]}
    return None


async def list_albums() -> list[dict]:
    """List all video albums in the community."""
    result = await vk_request("video.getAlbums", {"count": 100})
    if "response" in result:
        return result["response"].get("items", [])
    return []


async def get_album_by_title(title: str) -> dict | None:
    """Find album by exact title (case-insensitive)."""
    albums = await list_albums()
    for album in albums:
        if album.get("title", "").lower() == title.lower():
            return album
    return None


async def upload_video(file_path: str, title: str,
                       album_id: int | None = None,
                       description: str = "") -> dict | None:
    """
    Upload a video file to VK community.
    Returns dict with video_id and owner_id, or None on error.

    Flow:
    1. video.save → get upload_url
    2. POST file to upload_url
    3. Video is saved automatically
    """
    file_size = os.path.getsize(file_path)
    size_mb = file_size / (1024 * 1024)
    logger.info("Uploading to VK: %s (%.1f MB) album=%s", title, size_mb, album_id)

    # Step 1: Get upload URL
    save_params = {
        "name": title[:255],
        "description": description[:1000] if description else "",
    }
    if album_id:
        save_params["album_id"] = album_id

    result = await vk_request("video.save", save_params)
    if "error" in result:
        error_msg = result["error"].get("error_msg", str(result["error"]))
        logger.error("video.save failed: %s", error_msg)
        return None

    upload_url = result["response"]["upload_url"]
    video_id = result["response"]["video_id"]
    owner_id = result["response"]["owner_id"]

    # Step 2: Upload file
    try:
        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as f:
                # aiohttp supports file uploads via data parameter
                async with session.post(upload_url, data={"video_file": f}) as resp:
                    upload_result = await resp.json(content_type=None)

            if isinstance(upload_result, list) and len(upload_result) == 4:
                # VK returns [video_id, owner_id, ...] on success
                vid = upload_result[0]
                oid = upload_result[1]
                logger.info("Uploaded: video-%d_%d", oid, vid)
                return {"video_id": vid, "owner_id": oid}

            if isinstance(upload_result, dict):
                # Sometimes returns dict format
                vid = upload_result.get("video_id", video_id)
                oid = upload_result.get("owner_id", owner_id)
                if upload_result.get("error"):
                    logger.error("Upload failed: %s", upload_result)
                    return None
                logger.info("Uploaded: video-%d_%d", oid, vid)
                return {"video_id": vid, "owner_id": oid}

            logger.error("Unexpected upload response: %s", upload_result)
            return None

    except aiohttp.ClientError as e:
        logger.error("Upload network error: %s", e)
        return None
    except Exception as e:
        logger.error("Upload error: %s", e)
        return None
