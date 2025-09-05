import asyncpg
from typing import List, Tuple, Optional, Dict, Any
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

class Database:
    def __init__(self):
        self.pool = None

    async def create_pool(self):
        """Создает пул подключений к PostgreSQL"""
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        await self.init_tables()

    async def init_tables(self):
        """Инициализирует таблицы в базе данных"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    text TEXT NOT NULL,
                    image_path TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_messages (
                    id SERIAL PRIMARY KEY,
                    message_id INTEGER REFERENCES messages(id),
                    chat_id BIGINT NOT NULL,
                    send_time TIMESTAMP NOT NULL,
                    is_sent BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')

    async def add_message(self, text: str, image_path: Optional[str] = None) -> int:
        """Добавляет новое сообщение в базу и возвращает его ID"""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "INSERT INTO messages (text, image_path) VALUES ($1, $2) RETURNING id",
                text, image_path
            )

    async def get_all_messages(self) -> List[Dict]:
        """Возвращает все сообщения"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT id, text, image_path, created_at FROM messages ORDER BY created_at DESC"
            )
            return [dict(record) for record in records]

    async def get_message_by_id(self, message_id: int) -> Optional[Dict]:
        """Возвращает сообщение по ID"""
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT id, text, image_path FROM messages WHERE id = $1",
                message_id
            )
            return dict(record) if record else None

    async def get_all_chats(self) -> List[Dict]:
        """Возвращает все чаты"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT chat_id, title FROM chats WHERE is_active = TRUE ORDER BY title"
            )
            return [dict(record) for record in records]

    async def add_chat(self, chat_id: int, title: str) -> None:
        """Добавляет чат в базу"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chats (chat_id, title) VALUES ($1, $2) ON CONFLICT (chat_id) DO UPDATE SET title = $2, is_active = TRUE",
                chat_id, title
            )

    async def add_scheduled_message(self, message_id: int, chat_id: int, send_time: datetime) -> int:
        """Добавляет запланированную отправку"""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "INSERT INTO scheduled_messages (message_id, chat_id, send_time) VALUES ($1, $2, $3) RETURNING id",
                message_id, chat_id, send_time
            )

    async def get_pending_messages(self) -> List[Dict]:
        """Возвращает неотправленные запланированные сообщения"""
        async with self.pool.acquire() as conn:
            records = await conn.fetch('''
                SELECT sm.id, sm.message_id, sm.chat_id, sm.send_time, 
                       m.text, m.image_path, c.title as chat_title
                FROM scheduled_messages sm
                JOIN messages m ON sm.message_id = m.id
                JOIN chats c ON sm.chat_id = c.chat_id
                WHERE sm.is_sent = FALSE AND sm.send_time <= NOW()
                ORDER BY sm.send_time
            ''')
            return [dict(record) for record in records]

    async def mark_as_sent(self, scheduled_id: int):
        """Помечает сообщение как отправленное"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE scheduled_messages SET is_sent = TRUE WHERE id = $1",
                scheduled_id
            )

db = Database()