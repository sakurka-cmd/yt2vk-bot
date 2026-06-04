"""SQLite database for yt2vk bot."""

import json
import aiosqlite
import os
from datetime import datetime

from bot.config import DATABASE_URL

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    channel_title TEXT DEFAULT '',
    album_id INTEGER NOT NULL,
    quality TEXT DEFAULT '720',
    check_interval INTEGER DEFAULT 3600,
    last_check TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS processed_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_id TEXT NOT NULL UNIQUE,
    subscription_id INTEGER,
    title TEXT DEFAULT '',
    quality TEXT DEFAULT '720',
    vk_video_id INTEGER DEFAULT 0,
    vk_owner_id INTEGER DEFAULT 0,
    uploaded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS oneoff_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT 0,
    url TEXT NOT NULL,
    youtube_id TEXT DEFAULT '',
    album_id INTEGER DEFAULT 0,
    quality TEXT DEFAULT '720',
    status TEXT DEFAULT 'pending',
    title TEXT DEFAULT '',
    vk_video_id INTEGER DEFAULT 0,
    vk_owner_id INTEGER DEFAULT 0,
    error TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS fsm_states (
    peer_id INTEGER PRIMARY KEY,
    state TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_processed_ytid ON processed_videos(youtube_id);
CREATE INDEX IF NOT EXISTS idx_subs_active ON subscriptions(active, channel_id);
"""


async def init_db() -> aiosqlite.Connection:
    global _db
    os.makedirs(os.path.dirname(DATABASE_URL) or ".", exist_ok=True)
    _db = await aiosqlite.connect(DATABASE_URL)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA busy_timeout=5000")
    await _db.executescript(SCHEMA)
    await _db.commit()
    return _db


def get_db() -> aiosqlite.Connection:
    assert _db is not None, "Database not initialized"
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None


# ── FSM helpers ──────────────────────────────────────────────

async def save_fsm_state(peer_id: int, state: str, data: dict):
    db = get_db()
    await db.execute(
        "INSERT OR REPLACE INTO fsm_states (peer_id, state, data, updated_at) VALUES (?, ?, ?, datetime('now'))",
        (peer_id, state, json.dumps(data, ensure_ascii=False)),
    )
    await db.commit()


async def get_fsm_state(peer_id: int) -> tuple[str, dict]:
    db = get_db()
    cur = await db.execute("SELECT state, data FROM fsm_states WHERE peer_id=?", (peer_id,))
    row = await cur.fetchone()
    if row:
        return row["state"], json.loads(row["data"])
    return "", {}


async def clear_fsm_state(peer_id: int):
    db = get_db()
    await db.execute("DELETE FROM fsm_states WHERE peer_id=?", (peer_id,))
    await db.commit()


# ── Subscriptions CRUD ────────────────────────────────────────

async def add_subscription(channel_id: str, channel_title: str,
                            album_id: int, quality: str = "720",
                            check_interval: int = 3600) -> int:
    db = get_db()
    cur = await db.execute(
        "INSERT INTO subscriptions (channel_id, channel_title, album_id, quality, check_interval) VALUES (?,?,?,?,?)",
        (channel_id, channel_title, album_id, quality, check_interval),
    )
    await db.commit()
    return cur.lastrowid


async def list_subscriptions() -> list[dict]:
    db = get_db()
    cur = await db.execute(
        "SELECT id, channel_id, channel_title, album_id, quality, active, last_check, created_at FROM subscriptions ORDER BY id"
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_subscription(sub_id: int) -> dict | None:
    db = get_db()
    cur = await db.execute("SELECT * FROM subscriptions WHERE id=?", (sub_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def update_subscription_quality(sub_id: int, quality: str):
    db = get_db()
    await db.execute("UPDATE subscriptions SET quality=? WHERE id=?", (quality, sub_id))
    await db.commit()


async def toggle_subscription(sub_id: int, active: int):
    db = get_db()
    await db.execute("UPDATE subscriptions SET active=? WHERE id=?", (active, sub_id))
    await db.commit()


async def delete_subscription(sub_id: int):
    db = get_db()
    await db.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
    await db.commit()


async def update_last_check(sub_id: int):
    db = get_db()
    await db.execute("UPDATE subscriptions SET last_check=datetime('now') WHERE id=?", (sub_id,))
    await db.commit()


# ── Processed videos ─────────────────────────────────────────

async def is_video_processed(youtube_id: str) -> bool:
    db = get_db()
    cur = await db.execute("SELECT 1 FROM processed_videos WHERE youtube_id=?", (youtube_id,))
    return await cur.fetchone() is not None


async def mark_video_processed(youtube_id: str, subscription_id: int | None,
                               title: str, quality: str,
                               vk_video_id: int, vk_owner_id: int):
    db = get_db()
    await db.execute(
        "INSERT OR IGNORE INTO processed_videos (youtube_id, subscription_id, title, quality, vk_video_id, vk_owner_id) VALUES (?,?,?,?,?,?)",
        (youtube_id, subscription_id, title, quality, vk_video_id, vk_owner_id),
    )
    await db.commit()


# ── One-off tasks ────────────────────────────────────────────

async def create_task(user_id: int, url: str, youtube_id: str,
                       album_id: int, quality: str, title: str = "") -> int:
    db = get_db()
    cur = await db.execute(
        "INSERT INTO oneoff_tasks (user_id, url, youtube_id, album_id, quality, title) VALUES (?,?,?,?,?,?)",
        (user_id, url, youtube_id, album_id, quality, title),
    )
    await db.commit()
    return cur.lastrowid


async def update_task_status(task_id: int, status: str,
                              vk_video_id: int = 0, vk_owner_id: int = 0,
                              error: str = ""):
    db = get_db()
    await db.execute(
        "UPDATE oneoff_tasks SET status=?, vk_video_id=?, vk_owner_id=?, error=?, completed_at=datetime('now') WHERE id=?",
        (status, vk_video_id, vk_owner_id, error, task_id),
    )
    await db.commit()
