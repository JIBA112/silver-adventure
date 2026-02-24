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
        # 存储聊天记录表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_name TEXT,
                message TEXT,
                timestamp REAL
            )
        """)
        await db.commit()

async def save_history(chat_id: int, user_name: str, message: str):
    """记录消息，每个聊天室只保留最近50条"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO chat_history (chat_id, user_name, message, timestamp) VALUES (?, ?, ?, ?)",
            (chat_id, user_name, message, time.time()),
        )
        # 自动清理旧记录
        await db.execute(
            "DELETE FROM chat_history WHERE id IN (SELECT id FROM chat_history WHERE chat_id = ? ORDER BY id DESC LIMIT -1 OFFSET 50)",
            (chat_id,)
        )
        await db.commit()

async def get_history(chat_id: int, limit: int = 15):
    """获取最近的上下文"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_name, message FROM chat_history WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return rows[::-1]  # 转回正序

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
    mode = await get_setting("whitelist_mode", "all")
    if mode == "all":
        return True
    whitelist = await get_setting("whitelist", [])
    if chat_type == "private":
        return user_id in whitelist or str(user_id) in whitelist
    return chat_id in whitelist or str(chat_id) in whitelist
