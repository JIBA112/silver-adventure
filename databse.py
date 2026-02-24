import aiosqlite
import json
import time
from typing import Optional

DB_PATH = "bot_data.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER PRIMARY KEY,
                last_time REAL
            )
        """)
        await db.commit()


async def get_setting(key: str, default=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except Exception:
                    return row[0]
            return default


async def set_setting(key: str, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        await db.commit()


async def get_cooldown_remaining(user_id: int) -> float:
    """返回剩余冷却秒数，0 表示可以使用"""
    cooldown_seconds = await get_setting("cooldown", 10)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT last_time FROM cooldowns WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return 0
            elapsed = time.time() - row[0]
            remaining = cooldown_seconds - elapsed
            return max(0, remaining)


async def update_cooldown(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO cooldowns (user_id, last_time) VALUES (?, ?)",
            (user_id, time.time()),
        )
        await db.commit()


async def is_allowed(user_id: int, chat_id: int, chat_type: str) -> bool:
    """检查用户/群组是否在白名单内"""
    mode = await get_setting("whitelist_mode", "all")  # all / whitelist

    if mode == "all":
        return True

    whitelist = await get_setting("whitelist", [])

    # 私聊：检查用户ID
    if chat_type == "private":
        return user_id in whitelist or str(user_id) in whitelist

    # 群聊：检查群ID
    return chat_id in whitelist or str(chat_id) in whitelist
