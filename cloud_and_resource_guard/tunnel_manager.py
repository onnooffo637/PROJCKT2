"""
Autonomous Public HTTPS Tunnel & Telegram WebApp Link Manager.
Re-exports and wraps cloudflare_tunnel_manager for full backward compatibility.
"""

from __future__ import annotations

import logging
from typing import Optional
from cloud_and_resource_guard.cloudflare_tunnel_manager import cloudflare_manager

logger = logging.getLogger("Aether.CloudGuard.Tunnel")


class PublicTunnelManager:
    """
    Facade wrapper maintaining backward compatibility with PublicTunnelManager interface.
    """

    def get_public_base_url(self) -> str:
        return cloudflare_manager.get_base_url()

    def get_webapp_url(self) -> str:
        return cloudflare_manager.get_current_tunnel_url(cache_bust=True)

    def set_public_url(self, url: str) -> None:
        cloudflare_manager.update_live_url(url)

    async def start_autonomous_tunnel(self) -> Optional[str]:
        return await cloudflare_manager.start()

    async def register_telegram_menu_button(self) -> bool:
        return await cloudflare_manager.sync_telegram_menu_button()

    def stop(self) -> None:
        cloudflare_manager.stop()


tunnel_manager = PublicTunnelManager()
