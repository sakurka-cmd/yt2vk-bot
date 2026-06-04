"""yt-dlp wrapper for downloading YouTube videos."""

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path

from bot.config import QUALITIES, DEFAULT_QUALITY, MAX_FILE_SIZE, TMP_DIR

logger = logging.getLogger(__name__)

YOUTUBE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)"
    r"([a-zA-Z0-9_-]{11})"
)

CHANNEL_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?youtube\.com/(?:channel/|@|c/)([a-zA-Z0-9_-]+)"
)

# yt-dlp binary path
YTDLP_BIN = shutil.which("yt-dlp") or "yt-dlp"


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    m = YOUTUBE_URL_RE.search(url)
    return m.group(1) if m else None


def extract_channel_id(url: str) -> str | None:
    """Extract YouTube channel identifier from URL."""
    m = CHANNEL_URL_RE.search(url)
    return m.group(1) if m else None


def get_format_string(quality: str) -> str:
    """Get yt-dlp format string for quality level."""
    fmt = QUALITIES.get(quality, QUALITIES[DEFAULT_QUALITY])
    return f"{fmt} --merge-output-format mp4"


async def get_video_info(url: str) -> dict | None:
    """Get video metadata without downloading."""
    cmd = [
        YTDLP_BIN,
        "--dump-json",
        "--no-download",
        "--no-playlist",
        url,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            logger.error("yt-dlp info failed: %s", stderr.decode(errors="replace")[:500])
            return None
        import json
        info = json.loads(stdout.decode())
        return {
            "id": info.get("id", ""),
            "title": info.get("title", ""),
            "duration": info.get("duration", 0),
            "channel": info.get("channel", ""),
            "description": info.get("description", "")[:500],
            "thumbnail": info.get("thumbnail", ""),
            "filesize_approx": info.get("filesize_approx", 0),
        }
    except asyncio.TimeoutError:
        logger.error("yt-dlp info timeout for %s", url)
        return None
    except Exception as e:
        logger.error("yt-dlp info error: %s", e)
        return None


async def download_video(url: str, quality: str = DEFAULT_QUALITY) -> str | None:
    """Download video and return path to file. Caller must delete the file."""
    os.makedirs(TMP_DIR, exist_ok=True)

    fmt = get_format_string(quality)
    output_template = os.path.join(TMP_DIR, "%(id)s.%(ext)s")

    cmd = [
        YTDLP_BIN,
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--no-playlist",
        "--no-cache-dir",
        "--quiet",
        "--no-warnings",
        "--progress",  # Show progress for logging
        url,
    ]

    # Add max filesize if configured
    if MAX_FILE_SIZE > 0:
        cmd.extend(["--max-filesize", str(MAX_FILE_SIZE)])

    logger.info("Downloading: %s (quality: %s)", url, quality)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
        if proc.returncode != 0:
            err = stderr.decode(errors="replace")
            logger.error("yt-dlp download failed: %s", err[:500])
            # Check if file too large
            if "File is larger than max-filesize" in err:
                return "TOO_LARGE"
            return None

        # Find downloaded file
        video_id = extract_video_id(url)
        if video_id:
            for ext in ("mp4", "mkv", "webm", "flv"):
                path = os.path.join(TMP_DIR, f"{video_id}.{ext}")
                if os.path.exists(path):
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    logger.info("Downloaded: %s (%.1f MB)", path, size_mb)
                    return path

        # Fallback: find by glob
        for f in os.listdir(TMP_DIR):
            if video_id and video_id in f:
                path = os.path.join(TMP_DIR, f)
                logger.info("Downloaded (fallback): %s", path)
                return path

        logger.error("Downloaded file not found for %s", url)
        return None

    except asyncio.TimeoutError:
        logger.error("Download timeout for %s", url)
        return None
    except Exception as e:
        logger.error("Download error: %s", e)
        return None


async def get_channel_info(channel_url_or_id: str) -> dict | None:
    """Get channel metadata."""
    url = channel_url_or_id
    if not url.startswith("http"):
        url = f"https://www.youtube.com/@{url}"

    cmd = [YTDLP_BIN, "--dump-json", "--flat-playlist", "--playlist-items", "0", url]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            return None
        import json
        info = json.loads(stdout.decode())
        return {
            "id": info.get("channel_id", ""),
            "title": info.get("channel", ""),
            "uploader_id": info.get("uploader_id", ""),
        }
    except Exception:
        return None


def cleanup_file(path: str):
    """Delete downloaded file."""
    try:
        if path and os.path.exists(path) and path != "TOO_LARGE":
            os.remove(path)
            logger.info("Cleaned up: %s", path)
    except Exception as e:
        logger.warning("Cleanup error: %s", e)
