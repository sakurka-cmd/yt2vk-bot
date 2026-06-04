"""Configuration from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

VK_TOKEN: str = os.environ["VK_TOKEN"]
VK_GROUP_ID: int = int(os.environ["VK_GROUP_ID"])

DATABASE_URL: str = os.environ.get("DATABASE_URL", "data/yt2vk_bot.db")

CHECK_INTERVAL: int = int(os.environ.get("CHECK_INTERVAL", "3600"))
TMP_DIR: str = os.environ.get("TMP_DIR", "/tmp/yt2vk")
MAX_FILE_SIZE: int = int(os.environ.get("MAX_FILE_SIZE", "0"))  # 0 = no limit
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

QUALITIES = {
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "4k": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
}
DEFAULT_QUALITY = "720"

ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip()
]
