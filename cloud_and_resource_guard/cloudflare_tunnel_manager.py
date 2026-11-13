"""
Local Cloudflare Tunnel (cloudflared) Auto-Spawner, Watchdog & Telegram Menu Button Live Sync.
Project Aether-Human - Core Cloud & Resource Guard.

Orchestrates:
1. Subprocess management of cloudflared tunnel (--url http://127.0.0.1:{PORT} --no-autoupdate)
2. Live Regex extraction of https://*.trycloudflare.com endpoints
3. Central in-memory LIVE_TUNNEL_URL state with cache-busting version tags
4. Immediate global and per-user Telegram ChatMenuButton synchronization
5. Auto-healing background watchdog that recovers from drops and notifies The King
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import time
from typing import Dict, List, Optional
import httpx

from aether_human_core.config.settings import settings

logger = logging.getLogger("Aether.CloudGuard.CloudflareTunnel")


class CloudflareTunnelManager:
    """
    Automated supervisor for local Cloudflare tunnels and Telegram WebApp integration.
    """

    # Must have at least one hyphen and must NOT be https://api.trycloudflare.com
    TUNNEL_REGEX = re.compile(r"https://(?!api\.)[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)+\.trycloudflare\.com")

    def __init__(self):
        env_url = os.getenv("WEBAPP_PUBLIC_URL")
        if env_url and "api.trycloudflare.com" in env_url:
            env_url = None
        self.live_tunnel_url: Optional[str] = env_url
        self._process: Optional[asyncio.subprocess.Process] = None
        self._is_running: bool = False
        self._watchdog_task: Optional[asyncio.Task] = None
        self._user_synced_cache: Dict[int, float] = {}  # Tracks user_id -> last_sync_time
        self._last_reconnect_time: float = 0.0
        self._last_tunnel_update_time: float = time.time()
        self._load_persisted_url_if_valid()

    def _load_persisted_url_if_valid(self) -> None:
        if os.path.exists("webapp_url.json"):
            try:
                import json
                with open("webapp_url.json", "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    candidate = (saved.get("base_url") or saved.get("webapp_url", "")).replace("/webapp", "").rstrip("/")
                    if candidate.startswith("https://") and "api.trycloudflare.com" not in candidate:
                        self.live_tunnel_url = candidate
            except Exception:
                pass

    def get_current_tunnel_url(self, cache_bust: bool = True) -> str:
        """
        Returns the absolute /webapp endpoint URL with an optional cache-buster timestamp.
        Always checks webapp_url.json if in-memory URL is missing or invalid.
        """
        if not self.live_tunnel_url or "api.trycloudflare.com" in self.live_tunnel_url:
            self._load_persisted_url_if_valid()

        base = self.live_tunnel_url or f"http://127.0.0.1:{settings.admin_port}"
        base = base.split("?")[0].rstrip("/")
        if not base.endswith("/webapp"):
            base = f"{base}/webapp"

        if cache_bust:
            return f"{base}?v={int(time.time())}"
        return base

    def get_base_url(self) -> str:
        """
        Returns the root https://*.trycloudflare.com domain without path.
        """
        if not self.live_tunnel_url or "api.trycloudflare.com" in self.live_tunnel_url:
            self._load_persisted_url_if_valid()
        if self.live_tunnel_url:
            return self.live_tunnel_url.split("?")[0].replace("/webapp", "").rstrip("/")
        return f"http://127.0.0.1:{settings.admin_port}"

    def update_live_url(self, new_url: str) -> None:
        """
        Persists the newly discovered tunnel URL to memory, webapp_url.json, and .env.
        """
        clean_url = new_url.split("?")[0].replace("/webapp", "").rstrip("/")
        if "api.trycloudflare.com" in clean_url:
            logger.debug(f"Ignored internal Cloudflare API endpoint: {clean_url}")
            return
        self.live_tunnel_url = clean_url
        self._last_tunnel_update_time = time.time()
        # Invalidate per-user cache so every user gets re-synced with the fresh URL immediately
        self._user_synced_cache.clear()
        logger.info(f"🌐 [Cloudflare Tunnel] Central LIVE_TUNNEL_URL updated -> {self.live_tunnel_url}")

        # 1. Update webapp_url.json
        try:
            import json
            with open("webapp_url.json", "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "webapp_url": f"{self.live_tunnel_url}/webapp",
                        "base_url": self.live_tunnel_url,
                        "updated_at": time.time(),
                    },
                    f,
                    indent=2,
                )
        except Exception as exc:
            logger.debug(f"Could not write webapp_url.json: {exc}")

        # 2. Update .env file automatically
        self._sync_env_file(clean_url)

    def _sync_env_file(self, new_url: str) -> None:
        env_path = ".env"
        if not os.path.exists(env_path):
            return
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()

            if "WEBAPP_PUBLIC_URL=" in content:
                updated = re.sub(r"WEBAPP_PUBLIC_URL=.*", f"WEBAPP_PUBLIC_URL={new_url}", content)
            else:
                updated = content.rstrip() + f"\nWEBAPP_PUBLIC_URL={new_url}\n"

            with open(env_path, "w", encoding="utf-8") as f:
                f.write(updated)
            logger.debug(f"Updated .env with WEBAPP_PUBLIC_URL={new_url}")
        except Exception as exc:
            logger.warning(f"Failed to update .env with new tunnel URL: {exc}")

    async def start(self) -> Optional[str]:
        """
        Spawns or verifies the Cloudflare tunnel process and begins log inspection.
        """
        self._is_running = True

        # First verify if an existing tunnel URL in webapp_url.json is still healthy
        if os.path.exists("webapp_url.json"):
            try:
                import json
                with open("webapp_url.json", "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    candidate = saved_data.get("base_url") or saved_data.get("webapp_url", "").replace("/webapp", "")
                    if candidate.startswith("https://") and "api.trycloudflare.com" not in candidate:
                        if await self._verify_url_health(candidate):
                            logger.info(f"✨ Reusing verified healthy existing tunnel: {candidate}")
                            self.update_live_url(candidate)
                            await self.sync_telegram_menu_button()
                            self._start_watchdog()
                            return self.live_tunnel_url
            except Exception as e:
                logger.debug(f"Existing tunnel verification notice: {e}")

        # Locate cloudflared binary
        cloudflared_bin = self._find_cloudflared_binary()
        if not cloudflared_bin:
            logger.warning("cloudflared binary not found on system PATH or workspace root.")
            return None

        # Spawn cloudflared subprocess
        await self._spawn_subprocess(cloudflared_bin)
        self._start_watchdog()
        return self.live_tunnel_url

    def _find_cloudflared_binary(self) -> Optional[str]:
        workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(workspace_dir, "cloudflared.exe"),
            os.path.join(os.getcwd(), "cloudflared.exe"),
            shutil.which("cloudflared"),
        ]
        return next((c for c in candidates if c and os.path.exists(c)), None)

    async def _spawn_subprocess(self, binary_path: str) -> None:
        """
        Executes cloudflared tunnel command and extracts URL from output stream.
        """
        port = settings.admin_port
        cmd = [
            binary_path,
            "tunnel",
            "--url",
            f"http://127.0.0.1:{port}",
            "--no-autoupdate",
        ]
        logger.info(f"🚀 Spawning autonomous Cloudflare Tunnel: {' '.join(cmd)}")

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception as exc:
            logger.error(f"Failed to spawn cloudflared subprocess: {exc}")
            return

        async def _log_scanner():
            url_found = False
            while self._is_running and self._process and self._process.stdout:
                line_bytes = await self._process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="ignore")

                if not url_found:
                    match = self.TUNNEL_REGEX.search(line)
                    if match:
                        url_found = True
                        new_url = match.group(0).strip()
                        self.update_live_url(new_url)
                        logger.info(f"🎉 New Live Cloudflare Tunnel URL established: {new_url}")
                        await self.sync_telegram_menu_button()
                        await self._notify_king_tunnel_ready(new_url)

            if self._process:
                await self._process.wait()
                logger.warning("cloudflared process terminated.")

        asyncio.create_task(_log_scanner())

    async def _verify_url_health(self, url: str) -> bool:
        """
        Verifies if local and remote endpoints return 200 OK.
        """
        check_target = f"{url.rstrip('/')}/webapp"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(check_target)
                if res.status_code == 200 and "no tunnel" not in res.text.lower():
                    return True
        except Exception:
            pass
        return False

    async def sync_telegram_menu_button(self, specific_user_id: Optional[int] = None) -> bool:
        """
        Updates Telegram Bot MenuButton globally and per-user with cache-busting parameters.
        """
        if not self.live_tunnel_url or not self.live_tunnel_url.startswith("https://"):
            return False

        token = settings.telegram_bot_token
        if not token:
            return False

        current_url = self.get_current_tunnel_url(cache_bust=True)
        api_url = f"https://api.telegram.org/bot{token}/setChatMenuButton"

        menu_payload = {
            "type": "web_app",
            "text": "🎮 عمر Mini App",
            "web_app": {"url": current_url},
        }

        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                # 1. Update target user if specified
                if specific_user_id:
                    res = await client.post(
                        api_url,
                        json={"chat_id": specific_user_id, "menu_button": menu_payload},
                    )
                    self._user_synced_cache[specific_user_id] = time.time()
                    return res.status_code == 200 and res.json().get("ok", False)

                # 2. Update Global Default
                await client.post(api_url, json={"menu_button": menu_payload})
                logger.info(f"✨ Telegram Global Menu Button synced -> {current_url}")

                # 3. Explicitly update Super Admins, King, and Key Test Accounts
                target_admins = set(settings.super_admin_ids_list) | ({settings.the_king_user_id} if settings.the_king_user_id else set())
                for admin_id in target_admins:
                    try:
                        await client.post(
                            api_url,
                            json={"chat_id": admin_id, "menu_button": menu_payload},
                        )
                        self._user_synced_cache[admin_id] = time.time()
                    except Exception:
                        pass

                # 4. Synchronize Menu Button across all active factory sub-bots (globally & per-user)
                try:
                    from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
                    clean_webapp_url = self.get_current_tunnel_url(cache_bust=False)
                    asyncio.create_task(multi_bot_dispatcher.sync_all_menu_buttons(clean_webapp_url))
                except Exception:
                    pass

                return True
            except Exception as exc:
                logger.debug(f"Exception updating setChatMenuButton: {exc}")
                return False

    async def sync_user_if_needed(self, user_id: int) -> None:
        """
        Called in /start and on incoming messages to ensure mobile clients break stale cache.
        Debounced to once every 10 minutes per user, unless the tunnel URL itself has changed.
        """
        now = time.time()
        last_sync = self._user_synced_cache.get(user_id, 0.0)
        if last_sync < self._last_tunnel_update_time or (now - last_sync > 600):
            self._user_synced_cache[user_id] = now
            asyncio.create_task(self.sync_telegram_menu_button(specific_user_id=user_id))

    def _start_watchdog(self) -> None:
        """
        Launches background health monitor that checks tunnel responsiveness every 60-120 seconds.
        """
        if self._watchdog_task and not self._watchdog_task.done():
            return

        async def _watchdog_loop():
            logger.info("Autonomous Cloudflare Tunnel Watchdog activated (Health checks every 90s).")
            while self._is_running:
                await asyncio.sleep(90.0)
                if not self.live_tunnel_url or not self.live_tunnel_url.startswith("https://"):
                    continue

                is_healthy = await self._verify_url_health(self.live_tunnel_url)
                if not is_healthy:
                    logger.warning("🚨 Cloudflare Tunnel health check failed! Initiating auto-recovery...")
                    await self._restart_tunnel()

        self._watchdog_task = asyncio.create_task(_watchdog_loop())

    async def _restart_tunnel(self) -> None:
        """
        Gracefully terminates previous process and spawns a fresh tunnel.
        """
        now = time.time()
        if now - self._last_reconnect_time < 30:
            return  # Throttle rapid restarts
        self._last_reconnect_time = now

        if self._process:
            try:
                self._process.terminate()
                await asyncio.sleep(1.5)
            except Exception:
                pass

        bin_path = self._find_cloudflared_binary()
        if bin_path:
            await self._spawn_subprocess(bin_path)

    async def _notify_king_tunnel_ready(self, url: str) -> None:
        """
        Dispatches a clean notification to The Sovereign King with fresh inline button.
        """
        token = settings.telegram_bot_token
        king_id = settings.the_king_user_id
        if not token or not king_id:
            return

        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        text = (
            f"🚀 <b>تم تجديد وتثبيت نفق Cloudflare بنجاح!</b> 🌐\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ تم تحديث الرابط في ذاكرة النظام وزر القائمة (Menu Button) لجميع المستخدمين فورياً.\n\n"
            f"💡 <b>ملاحظة:</b> يمكنك الآن فتح الـ Mini App من الزر أدناه مباشرة."
        )
        markup = {
            "inline_keyboard": [
                [{"text": "🎮 فتح Mini App عمر", "web_app": {"url": self.get_current_tunnel_url(cache_bust=True)}}],
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(
                    api_url,
                    json={
                        "chat_id": king_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": markup,
                    },
                )
        except Exception as e:
            logger.debug(f"Could not notify King of fresh tunnel: {e}")

    def stop(self) -> None:
        self._is_running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass


cloudflare_manager = CloudflareTunnelManager()

