"""
PROJECT "AETHER-HUMAN"
Autonomous Sentient-Like Telegram Entity (Monorepo Master Entrypoint)

Orchestrates:
1. Relational Database Layer (PostgreSQL / SQLite)
2. Social Knowledge Graph (Neo4j / GraphRAG)
3. Episodic & Semantic Vector Store (Qdrant)
4. Neuro-Endocrine & Psychological Hormone Engine
5. Cognitive Maestro & Pre-Conscious Inner Monologue (Gemini Key Pool)
6. Multimodal Visual Identity & Acoustic Voice Synthesis
7. Telegram MTProto Userbot Client (Telethon)
8. Autonomous Proactive Daemons & Nightly REM Dreaming
9. Admin Observatory FastAPI Web & WebSockets Telemetry Server
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import uvicorn

# Configure UTF-8 for console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from aether_human_core.config.settings import settings
from aether_human_core.config.llm_router import llm_pool
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.neo4j_graph.social_graph import social_graph
from aether_human_core.database.vector_store.qdrant_client import vector_memory
from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
from aether_human_core.autonomous_daemon.proactive_initiator import proactive_daemon
from aether_human_core.autonomous_daemon.memory_consolidation import memory_consolidation_daemon
from aether_human_core.daemons.story_daemon import story_daemon
from aether_human_core.admin_observatory.server import app
from cloud_and_resource_guard import resource_governor, tunnel_manager

# Ensure logs directory exists and configure file + stream logging with sensitive data masking (Task B5)
import re

class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = re.sub(r'bot\d+:[A-Za-z0-9_-]+', 'bot[REDACTED_TOKEN]', record.msg)
            record.msg = re.sub(r'key=[^&\s"]+', 'key=[REDACTED_KEY]', record.msg)
        return True

os.makedirs("logs", exist_ok=True)
_file_handler = logging.FileHandler("logs/aether_system.log", encoding="utf-8")
_stream_handler = logging.StreamHandler(sys.stdout)
_mask_filter = SensitiveDataFilter()
_file_handler.addFilter(_mask_filter)
_stream_handler.addFilter(_mask_filter)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[_stream_handler, _file_handler],
)

# Task B5: Suppress overly verbose third-party HTTP transport logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("Aether.Core.Main")


class AetherSystemMaster:
    """
    Main Application Supervisor lifecycle manager.
    """
    def __init__(self):
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        logger.info("=" * 70)
        logger.info("🌟 INITIATING PROJECT AETHER-HUMAN CORE ENGINE 🌟")
        logger.info(f"Identity: Omar (عمر) | Age: 24 | Cairo, Egypt")
        logger.info(f"Gemini API Key Pool: {len(settings.gemini_keys_list)} active rotation keys")
        logger.info("=" * 70)

        # 0. Align Core VoIP Event Loop
        from live_voip_call_engine.full_duplex_pipeline import full_duplex_pipeline
        full_duplex_pipeline._main_loop = asyncio.get_running_loop()

        # 1. Initialize Relational Storage Schema
        logger.info("[1/7] Initializing Relational PostgreSQL/SQLite Data Access Layer...")
        await db_manager.init_schema()

        # 2. Initialize Neo4j Social Knowledge Graph
        logger.info("[2/7] Connecting to Neo4j Social Knowledge Graph...")
        await social_graph.initialize()

        # 3. Initialize Long-Term Episodic Vector Store
        logger.info("[3/7] Initializing Qdrant Episodic Long-Term Memory...")
        await vector_memory.initialize()

        # 4. Initialize Telegram MTProto Userbot Client
        logger.info("[4/7] Launching Telegram MTProto Userbot Client...")
        await mtproto_manager.initialize()

        # 4.5 Initialize Forum Topics Manager, Outbound VoIP Scheduler & Multi-Bot Dispatcher
        from admin_telemetry_and_archiver.forum_topics_manager import forum_topics_manager
        from live_voip_call_engine.outbound_call_scheduler import outbound_scheduler
        from bot_factory.interactive_userbot_auth import interactive_userbot
        from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
        await forum_topics_manager.initialize_topics()
        outbound_scheduler.start_scheduler_worker()
        interactive_userbot.start_background_init()
        multi_bot_dispatcher.start_dispatcher()

        # 5. Launch Autonomous Subconscious Daemons & Cloud Resource Governor
        logger.info("[5/7] Activating Proactive Initiator, Nightly Dream Daemons & Cloud Governor...")
        proactive_daemon.start()
        memory_consolidation_daemon.start()
        story_daemon.start()
        resource_governor.start_background_monitoring()

        # 6. Launch Admin Observatory Server
        server_task = None
        server = None
        async def _safe_serve(srv):
            try:
                await srv.serve()
            except Exception as e:
                logger.warning(f"Admin Observatory UI notice: {e}")

        try:
            config = uvicorn.Config(
                app=app,
                host=settings.admin_host,
                port=settings.admin_port,
                log_level="warning",
                loop="asyncio",
            )
            server = uvicorn.Server(config)
            server_task = asyncio.create_task(_safe_serve(server))
            logger.info(f"[6/7] Starting Admin Observatory on http://localhost:{settings.admin_port} ...")
        except Exception as exc:
            logger.warning(f"Could not bind Admin Observatory on port {settings.admin_port}: {exc}")

        # 6.5 Launch Autonomous Public HTTPS Tunnel for Telegram Mini App
        logger.info("[6.5/7] Establishing Autonomous HTTPS Tunnel & Telegram WebApp Menu Button...")
        await tunnel_manager.start_autonomous_tunnel()

        logger.info("[7/7] ✨ All micro-engines successfully synchronized and alive.")

        # Keep running until termination signal
        try:
            await self._shutdown_event.wait()
        finally:
            logger.info("Graceful shutdown initiated...")
            try:
                multi_bot_dispatcher.stop_all()
            except Exception:
                pass
            try:
                tunnel_manager.stop()
            except Exception:
                pass
            try:
                resource_governor.stop()
            except Exception:
                pass
            try:
                proactive_daemon.stop()
            except Exception:
                pass
            try:
                memory_consolidation_daemon.stop()
            except Exception:
                pass
            try:
                story_daemon.stop()
            except Exception:
                pass
            try:
                await mtproto_manager.close()
            except Exception:
                pass
            try:
                if interactive_userbot.client:
                    await interactive_userbot.client.disconnect()
            except Exception:
                pass
            try:
                await llm_pool.close()
            except Exception:
                pass
            try:
                await db_manager.close()
            except Exception:
                pass
            if server:
                server.should_exit = True
            if server_task:
                try:
                    await server_task
                except Exception:
                    pass
            logger.info("Aether-Human Core shutdown complete.")

    def request_shutdown(self) -> None:
        self._shutdown_event.set()


async def main():
    master = AetherSystemMaster()

    # Register OS signal handlers if supported on the current platform
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, master.request_shutdown)
        except NotImplementedError:
            pass  # Windows signals handled through loop exceptions

    try:
        await master.start()
    except (KeyboardInterrupt, asyncio.CancelledError):
        master.request_shutdown()
    except Exception as exc:
        logger.critical(f"AetherSystemMaster unexpected error: {exc}", exc_info=True)
        master.request_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        import traceback
        traceback.print_exc()
        sys.exit(1)
