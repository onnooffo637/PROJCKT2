"""
Passive Omni-Archiver (Project Aether-Human - Admin Omni-Observatory)
Ultra-high-throughput message archival engine with real-time Zstandard compression.
Harvests and preserves every communication event across all groups and DMs forever.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from aether_human_core.config.settings import settings

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    import zlib
    HAS_ZSTD = False

logger = logging.getLogger("Aether.Observatory.OmniArchiver")


class PassiveOmniArchiver:
    """
    Stores full-fidelity message telemetry in compressed archives.
    """

    def __init__(self, base_dir: str = "data/archives"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._cctx = zstd.ZstdCompressor(level=3) if HAS_ZSTD else None

    def _get_daily_archive_path(self) -> str:
        today_str = datetime.datetime.now().strftime("%Y_%m_%d")
        ext = "zst.jsonl" if HAS_ZSTD else "zlib.jsonl"
        return os.path.join(self.base_dir, f"omni_messages_{today_str}.{ext}")

    def archive_message(
        self,
        message_id: int,
        chat_id: int,
        chat_title: str,
        chat_type: str,
        sender_id: int,
        sender_name: str,
        sender_username: Optional[str],
        message_text: str,
        media_type: str = "text",
    ) -> None:
        """
        Appends compressed record to daily archive file.
        """
        if chat_id == settings.admin_telemetry_supergroup_id:
            return

        record = {
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().isoformat(),
            "message_id": message_id,
            "chat_id": chat_id,
            "chat_title": chat_title,
            "chat_type": chat_type,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "sender_username": sender_username,
            "message_text": message_text,
            "media_type": media_type,
        }

        try:
            line = json.dumps(record, ensure_ascii=False) + "\n"
            raw_bytes = line.encode("utf-8")

            if HAS_ZSTD and self._cctx:
                compressed_chunk = self._cctx.compress(raw_bytes)
            else:
                import zlib
                compressed_chunk = zlib.compress(raw_bytes)

            archive_path = self._get_daily_archive_path()
            with open(archive_path, "ab") as f:
                # Prepend 4-byte chunk size header
                chunk_len = len(compressed_chunk)
                f.write(chunk_len.to_bytes(4, byteorder="big"))
                f.write(compressed_chunk)

        except Exception as exc:
            logger.error(f"Failed to archive message {message_id}: {exc}")

    def search_user_archive(
        self,
        sender_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Iterates over recent archives to collect user messages.
        """
        results = []
        if not os.path.exists(self.base_dir):
            return results

        files = sorted(os.listdir(self.base_dir), reverse=True)
        dctx = zstd.ZstdDecompressor() if HAS_ZSTD else None

        for filename in files[:7]:  # Scan up to past 7 daily archives
            path = os.path.join(self.base_dir, filename)
            try:
                with open(path, "rb") as f:
                    while True:
                        len_bytes = f.read(4)
                        if not len_bytes or len(len_bytes) < 4:
                            break
                        chunk_len = int.from_bytes(len_bytes, byteorder="big")
                        chunk = f.read(chunk_len)
                        if len(chunk) < chunk_len:
                            break

                        if HAS_ZSTD and dctx:
                            decompressed = dctx.decompress(chunk)
                        else:
                            import zlib
                            decompressed = zlib.decompress(chunk)

                        rec = json.loads(decompressed.decode("utf-8"))
                        if rec.get("sender_id") == sender_id:
                            results.append(rec)
                            if len(results) >= limit:
                                return results
            except Exception as e:
                logger.debug(f"Error reading archive {filename}: {e}")

        return results


omni_archiver = PassiveOmniArchiver()

