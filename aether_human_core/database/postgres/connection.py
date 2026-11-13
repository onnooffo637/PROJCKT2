"""
Asynchronous Database Connection and Session Lifecycle for Project Aether-Human.
Compatible with PostgreSQL (asyncpg) and SQLite (aiosqlite) for standalone environments.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool
from sqlalchemy import event

from aether_human_core.config.settings import settings

logger = logging.getLogger("Aether.DB.Postgres")

Base = declarative_base()


class DatabaseManager:
    """
    Manages async database engine lifecycle, connection pooling, and session creation.
    Optimized for high-concurrency SQLite (WAL mode, 60s busy timeout) and PostgreSQL.
    """
    def __init__(self, db_url: str):
        self.db_url: str = db_url
        is_sqlite = "sqlite" in self.db_url
        connect_args = {"timeout": 60, "check_same_thread": False} if is_sqlite else {}
        
        self.engine: AsyncEngine = create_async_engine(
            self.db_url,
            echo=settings.debug,
            future=True,
            connect_args=connect_args,
            poolclass=AsyncAdaptedQueuePool,
            pool_size=20,
            max_overflow=30,
            pool_timeout=60,
            pool_pre_ping=not is_sqlite,
        )

        if is_sqlite:
            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                try:
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.execute("PRAGMA busy_timeout=60000")
                    cursor.execute("PRAGMA temp_store=MEMORY")
                    cursor.close()
                except Exception as p_err:
                    logger.debug(f"SQLite PRAGMA setup note: {p_err}")

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        logger.info(f"DatabaseManager initialized with backend URL scheme: {self.db_url.split('://')[0]}")

    async def init_schema(self) -> None:
        """
        Creates all defined database tables if they do not exist,
        and applies automatic non-destructive schema migrations.
        """
        async with self.engine.begin() as conn:
            logger.info("Verifying and building relational database schema...")
            await conn.run_sync(Base.metadata.create_all)

            def apply_safe_migrations(sync_conn):
                try:
                    if "sqlite" in self.db_url:
                        cursor = sync_conn.connection.cursor()
                        cursor.execute("PRAGMA table_info(users)")
                        existing_cols = [row[1] for row in cursor.fetchall()]
                        if "role" not in existing_cols:
                            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'MEMBER'")
                        if "role_assigned_by" not in existing_cols:
                            cursor.execute("ALTER TABLE users ADD COLUMN role_assigned_by BIGINT")
                        if "custom_title" not in existing_cols:
                            cursor.execute("ALTER TABLE users ADD COLUMN custom_title VARCHAR(128)")

                        cursor.execute("PRAGMA table_info(chats)")
                        chat_cols = [row[1] for row in cursor.fetchall()]
                        if "telegram_id" not in chat_cols:
                            cursor.execute("ALTER TABLE chats ADD COLUMN telegram_id BIGINT")
                            cursor.execute("UPDATE chats SET telegram_id = chat_id WHERE telegram_id IS NULL")
                        if "updated_at" not in chat_cols:
                            cursor.execute("ALTER TABLE chats ADD COLUMN updated_at DATETIME")
                            cursor.execute("UPDATE chats SET updated_at = coalesce(last_message_at, created_at) WHERE updated_at IS NULL")

                        cursor.execute("PRAGMA table_info(messages)")
                        msg_cols = [row[1] for row in cursor.fetchall()]
                        if "reply_to_msg_id" not in msg_cols:
                            cursor.execute("ALTER TABLE messages ADD COLUMN reply_to_msg_id BIGINT")
                        if "media_type" not in msg_cols:
                            cursor.execute("ALTER TABLE messages ADD COLUMN media_type VARCHAR(32) DEFAULT 'text'")
                        cursor.close()
                except Exception as ex:
                    logger.debug(f"Migration step note: {ex}")

            await conn.run_sync(apply_safe_migrations)
            logger.info("Relational database schema ready.")

    async def close(self) -> None:
        """
        Closes connection pool.
        """
        await self.engine.dispose()
        logger.info("Database engine connections closed.")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Yields a transactional AsyncSession context.
        Rolls back automatically on unhandled exceptions.
        Retries commit with exponential backoff if database is temporarily locked.
        """
        session: AsyncSession = self.session_factory()
        try:
            yield session
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await session.commit()
                    break
                except Exception as c_err:
                    err_str = str(c_err).lower()
                    if ("locked" in err_str or "busy" in err_str) and attempt < max_retries - 1:
                        await asyncio.sleep(0.3 * (attempt + 1))
                        continue
                    raise
        except Exception as exc:
            try:
                await session.rollback()
            except Exception:
                pass
            logger.error(f"Database session exception encountered. Transaction rolled back: {exc}")
            raise
        finally:
            await session.close()


# Global DB Manager
db_manager = DatabaseManager(settings.postgres_url)
session_scope = db_manager.session
