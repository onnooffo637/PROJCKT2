"""
Cloud Resource & Railway Health Governor for Project Aether-Human (V2.0).
Monitors CPU/RAM footprint, performs background garbage collection,
enforces anti-OOM circuit breakers, and provides cloud liveness/readiness probes.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import time
from typing import Dict, Any, Optional
import psutil
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from aether_human_core.cognitive_engine.cognitive_cache import cognitive_cache
from gemini_load_balancer.key_pool_manager import semantic_cache, message_debouncer

logger = logging.getLogger("Aether.CloudGuard.Governor")


class HealthReport(BaseModel):
    status: str
    service: str = "AETHER-HUMAN-DUAL-CORE"
    uptime_seconds: float
    memory_rss_mb: float
    memory_vms_mb: float
    memory_percent: float
    cpu_percent: float
    thread_count: int
    gc_collections_run: int
    active_coro_tasks: int
    cache_entries: int


class RailwayHealthGovernor:
    """
    Supervises system health and prevents memory leaks or container termination.
    """

    def __init__(
        self,
        rss_memory_limit_mb: float = 450.0,
        check_interval_seconds: float = 45.0,
    ):
        self.rss_memory_limit_mb = rss_memory_limit_mb
        self.check_interval_seconds = check_interval_seconds
        self.start_time = time.time()
        self.gc_collections_count = 0
        self._process = psutil.Process(os.getpid())
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_running = False

    def start_background_monitoring(self) -> None:
        """
        Starts the asynchronous memory governance loop.
        """
        if self._is_running:
            return
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._governor_loop())
        logger.info(f"Railway Health Governor activated (RSS threshold: {self.rss_memory_limit_mb} MB).")

    def stop(self) -> None:
        self._is_running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()

    async def _governor_loop(self) -> None:
        while self._is_running:
            try:
                await asyncio.sleep(self.check_interval_seconds)
                # Sample memory
                mem_info = self._process.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)

                # Periodic routine GC
                collected = gc.collect()
                self.gc_collections_count += 1

                # If RSS exceeds threshold, trigger emergency memory eviction
                if rss_mb > self.rss_memory_limit_mb:
                    logger.warning(
                        f"🚨 MEMORY THRESHOLD EXCEEDED: {rss_mb:.1f} MB > {self.rss_memory_limit_mb} MB! "
                        "Triggering emergency cache eviction and GC."
                    )
                    self.perform_emergency_pruning()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Governor loop error: {exc}")

    def perform_emergency_pruning(self) -> Dict[str, Any]:
        """
        Evicts non-critical in-memory caches to save container RAM.
        """
        # Clear cognitive cache
        cleared_cog = len(cognitive_cache._cache)
        cognitive_cache._cache.clear()

        # Clear semantic cache
        cleared_sem = len(semantic_cache._cache)
        semantic_cache._cache.clear()

        # Clear debouncer queue
        cleared_deb = len(message_debouncer._pending_buffers)
        message_debouncer._pending_buffers.clear()

        # Force aggressive cyclic garbage collection across all 3 generations
        collected = gc.collect(0) + gc.collect(1) + gc.collect(2)
        self.gc_collections_count += 1

        mem_info = self._process.memory_info()
        rss_after = mem_info.rss / (1024 * 1024)

        logger.info(
            f"Emergency pruning complete. Freed {collected} objects. Current RSS: {rss_after:.1f} MB."
        )
        return {
            "freed_objects": collected,
            "pruned_cognitive_cache": cleared_cog,
            "pruned_semantic_cache": cleared_sem,
            "pruned_debouncer_queues": cleared_deb,
            "current_rss_mb": round(rss_after, 2),
        }

    def get_health_metrics(self) -> HealthReport:
        """
        Returns live operational telemetry report.
        """
        mem_info = self._process.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)
        vms_mb = mem_info.vms / (1024 * 1024)

        try:
            cpu_percent = self._process.cpu_percent(interval=0.0)
        except Exception:
            cpu_percent = 0.0

        try:
            tasks_count = len(asyncio.all_tasks())
        except Exception:
            tasks_count = 0

        cache_total = (
            len(cognitive_cache._cache) +
            len(semantic_cache._cache) +
            len(message_debouncer._pending_buffers)
        )

        return HealthReport(
            status="healthy" if rss_mb < self.rss_memory_limit_mb else "degraded_high_memory",
            uptime_seconds=round(time.time() - self.start_time, 2),
            memory_rss_mb=round(rss_mb, 2),
            memory_vms_mb=round(vms_mb, 2),
            memory_percent=round(self._process.memory_percent(), 2),
            cpu_percent=round(cpu_percent, 2),
            thread_count=self._process.num_threads(),
            gc_collections_run=self.gc_collections_count,
            active_coro_tasks=tasks_count,
            cache_entries=cache_total,
        )


# Singleton
resource_governor = RailwayHealthGovernor()

# Fast APIRouter for Cloud Probes
health_router = APIRouter(prefix="", tags=["Health & Governance"])


@health_router.get("/health", status_code=status.HTTP_200_OK)
async def liveness_probe() -> Dict[str, str]:
    """Fast liveness check for Railway / Render / Kubernetes / Docker."""
    return {"status": "ok", "service": "AETHER-HUMAN-DUAL-CORE"}


@health_router.get("/health/metrics", response_model=HealthReport)
async def detailed_metrics() -> HealthReport:
    """Detailed resource consumption metrics."""
    return resource_governor.get_health_metrics()


@health_router.post("/health/gc")
async def trigger_manual_gc(admin_secret: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Allows manual memory sweep and cache purge."""
    return resource_governor.perform_emergency_pruning()
