"""
PART 3 — Autonomous Story Daemon Hook + Deep Multimodal Vision (Stickers, GIFs, Photos & Files)
Patches:
  - main.py
  - aether_human_core/telegram_client/handlers/media_handler.py
  - aether_human_core/telegram_client/mtproto_manager.py
  - bot_factory/multi_bot_dispatcher.py
  - aether_human_core/cognitive_engine/orchestrator.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\monsm\Downloads\New folder (6)\New folder"
MAIN = ROOT + r"\main.py"
MEDH = ROOT + r"\aether_human_core\telegram_client\handlers\media_handler.py"
MTPR = ROOT + r"\aether_human_core\telegram_client\mtproto_manager.py"
MBDP = ROOT + r"\bot_factory\multi_bot_dispatcher.py"
ORCH = ROOT + r"\aether_human_core\cognitive_engine\orchestrator.py"


def rw(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def ww(p, s):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sub(src, old, new, label):
    nl = "\r\n" if "\r\n" in src else "\n"
    o = old.replace("\r\n", "\n").replace("\n", nl)
    n = new.replace("\r\n", "\n").replace("\n", nl)
    if o in src:
        print(f"✅ {label}")
        return src.replace(o, n, 1)
    print(f"⚠️  {label} — anchor NOT found")
    return src


# ───────────────────────── 1. main.py ─────────────────────────
m = rw(MAIN)
m = sub(m,
"""from aether_human_core.autonomous_daemon.proactive_initiator import proactive_daemon
from aether_human_core.autonomous_daemon.memory_consolidation import memory_consolidation_daemon""",
"""from aether_human_core.autonomous_daemon.proactive_initiator import proactive_daemon
from aether_human_core.autonomous_daemon.memory_consolidation import memory_consolidation_daemon
from aether_human_core.daemons.story_daemon import story_daemon""",
"main: import story_daemon")

m = sub(m,
"""        proactive_daemon.start()
        memory_consolidation_daemon.start()
        resource_governor.start_background_monitoring()""",
"""        proactive_daemon.start()
        memory_consolidation_daemon.start()
        story_daemon.start()
        resource_governor.start_background_monitoring()""",
"main: story_daemon.start()")

m = sub(m,
"""            proactive_daemon.stop()
            memory_consolidation_daemon.stop()""",
"""            proactive_daemon.stop()
            memory_consolidation_daemon.stop()
            story_daemon.stop()""",
"main: story_daemon.stop()")
ww(MAIN, m)

# ───────────────────────── 2. media_handler.py ─────────────────────────
mh = rw(MEDH)
mh = sub(mh,
"""import logging
import random
from typing import Optional""",
"""import asyncio
import base64
import io
import logging
import os
import random
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple""",
"media_handler: expanded imports for multimodal vision & file extraction")

MULTIMODAL_VISION_METHODS = '''
    # =========================================================================
    # TASK 3.2: True Visual Sticker, Animated Sticker/GIF, Image & File Vision
    # =========================================================================

    SUPPORTED_TEXT_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".txt", ".json", ".md", ".csv",
        ".log", ".pdf", ".html", ".htm", ".css", ".yaml", ".yml", ".xml",
        ".sh", ".bat", ".ps1", ".sql", ".c", ".cpp", ".h", ".java", ".go",
        ".rs", ".php", ".rb", ".ini", ".env", ".toml",
    }

    @classmethod
    async def extract_keyframes_with_ffmpeg(
        cls,
        video_bytes: bytes,
        ext: str = ".webm",
        max_frames: int = 2,
    ) -> List[Tuple[bytes, str]]:
        """
        Extracts 1-2 visual JPEG keyframes from a .webm video sticker or .mp4 GIF animation
        using FFmpeg in a non-blocking subprocess.
        """
        if not video_bytes:
            return []
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            return []

        cache_dir = os.path.join(os.getcwd(), "artifacts", "vision_cache")
        os.makedirs(cache_dir, exist_ok=True)
        uid = f"{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        in_path = os.path.join(cache_dir, f"in_{uid}{ext}")
        out_pattern = os.path.join(cache_dir, f"frame_{uid}_%d.jpg")

        frames: List[Tuple[bytes, str]] = []
        try:
            with open(in_path, "wb") as f:
                f.write(video_bytes)

            cmd = [
                ffmpeg_bin, "-y", "-i", in_path,
                "-vf", "scale=512:-1",
                "-vframes", str(max_frames),
                "-q:v", "4",
                out_pattern,
            ]
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8.0,
            )

            for idx in range(1, max_frames + 1):
                fp = os.path.join(cache_dir, f"frame_{uid}_{idx}.jpg")
                if os.path.exists(fp):
                    with open(fp, "rb") as rf:
                        data = rf.read()
                    if data:
                        frames.append((data, "image/jpeg"))
        except Exception as exc:
            logger.debug(f"FFmpeg keyframe extraction notice: {exc}")
        finally:
            try:
                if os.path.exists(in_path):
                    os.remove(in_path)
            except Exception:
                pass
            for idx in range(1, max_frames + 2):
                fp = os.path.join(cache_dir, f"frame_{uid}_{idx}.jpg")
                try:
                    if os.path.exists(fp):
                        os.remove(fp)
                except Exception:
                    pass

        return frames

    @classmethod
    async def analyze_visual_media_with_gemini(
        cls,
        visual_frames: List[Tuple[bytes, str]],
        media_kind: str = "sticker",
        sticker_emoji: str = "",
        user_caption: str = "",
    ) -> str:
        """
        Passes 1-3 visual frames (image/webp or image/jpeg) to Gemini Vision via inline_data
        and returns an enriched description of the actual sticker/GIF/photo content.
        """
        from aether_human_core.config.llm_router import llm_pool

        valid_parts: List[Dict[str, Any]] = []
        for raw_bytes, mime_type in visual_frames:
            if not raw_bytes:
                continue
            b64_str = base64.b64encode(raw_bytes).decode("utf-8")
            valid_parts.append(
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": b64_str,
                    }
                }
            )

        if not valid_parts:
            if media_kind == "sticker":
                return f"[ملصق تعبيري: {sticker_emoji or '✨'}]"
            return user_caption or "[صورة]"

        if media_kind in ("sticker", "gif"):
            vision_prompt = (
                "انظر إلى صورة هذا الملصق/الـ GIF المرفق، افهم الريأكشن أو الميم أو الشكل المرسوم بداخله فعلياً "
                "(وليس مجرد الإيموجي)، واكتب وصفاً دقيقاً ومختصراً في جملة واحدة لما يظهر في الملصق "
                "(تعابير الوجه، الحركة، الشخصية، أو الكلام المكتوب داخله):"
            )
        else:
            vision_prompt = (
                "انظر إلى هذه الصورة المرسلة من المستخدم بدقة، وصف كل ما يظهر فيها بوضوح "
                "(الأشخاص، الأشياء، النصوص أو الأكواد البرمجية إن وجدت، المكان، أو الميم) في جملتين مختصرتين:"
            )

        try:
            vision_desc = await llm_pool.generate_content(
                prompt=vision_prompt,
                media_parts=valid_parts,
                temperature=0.3,
                max_tokens=300,
            )
            vision_desc = (vision_desc or "").strip().replace("\\n", " ")
        except Exception as exc:
            logger.warning(f"Gemini Vision analysis fallback ({exc}).")
            vision_desc = ""

        if media_kind in ("sticker", "gif"):
            label = "ملصق مرئي" if media_kind == "sticker" else "صورة متحركة GIF"
            if vision_desc:
                enriched = (
                    f"[{label} {sticker_emoji} - المحتوى البصري المرسوم داخل الملصق فعلياً: ({vision_desc}). "
                    f"تفاعل مع فكرة الملصق أو الريأكشن المرسوم فيه بطبيعية وخفة دم حسب شخصيتك]"
                )
            else:
                enriched = f"[{label}: {sticker_emoji or '✨'}]"
            if user_caption:
                enriched += f" {user_caption}"
            logger.info(f"👁️ [Gemini Vision Sticker/GIF] Parsed visual content: '{vision_desc[:80]}'")
            return enriched

        # Photo
        if vision_desc:
            enriched = (
                f"[صورة أرسلها المستخدم - ما يظهر في الصورة فعلياً بعد رؤيتها: ({vision_desc})]"
            )
            if user_caption:
                enriched += f" تعليق المستخدم مع الصورة: {user_caption}"
            else:
                enriched += " علق على الصورة وتفاعل مع ما يظهر فيها بطبيعية كإنسان شايفها قدامه."
            logger.info(f"👁️ [Gemini Vision Photo] Parsed photo content: '{vision_desc[:80]}'")
            return enriched
        return user_caption or "[صورة]"

    @classmethod
    def extract_document_text(
        cls,
        file_bytes: bytes,
        file_name: str,
        user_caption: str = "",
        max_chars: int = 30000,
    ) -> Optional[str]:
        """
        Task 3.2 (2) — Extracts text/code from uploaded Documents (.py, .js, .txt, .json,
        .md, .csv, .log, .pdf, .html, etc.) up to 30,000 chars and wraps inside
        <ATTACHED_FILE name="...">...</ATTACHED_FILE>.
        """
        if not file_bytes:
            return None

        safe_name = os.path.basename(file_name or "attached_file.txt")
        _, ext = os.path.splitext(safe_name.lower())

        extracted = ""
        if ext == ".pdf":
            try:
                import pypdf  # type: ignore
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pages_txt: List[str] = []
                total_len = 0
                for page in reader.pages:
                    pt = page.extract_text() or ""
                    if pt:
                        pages_txt.append(pt)
                        total_len += len(pt)
                        if total_len >= max_chars:
                            break
                extracted = "\\n".join(pages_txt)
            except Exception as pdf_err:
                logger.warning(f"PDF text extraction error for [{safe_name}]: {pdf_err}")
                return None
        else:
            for enc in ("utf-8", "utf-8-sig", "cp1256", "latin-1"):
                try:
                    extracted = file_bytes.decode(enc)
                    break
                except Exception:
                    continue

        extracted = (extracted or "").strip()
        if not extracted:
            return None

        if len(extracted) > max_chars:
            extracted = extracted[:max_chars] + "\\n... [تم اقتصاص باقي الملف لطوله]"

        caption_instruction = user_caption.strip() if user_caption else "اقرأ هذا الملف المرفق وافهم محتواه أو الكود بداخله ورد على المستخدم بخصوصه."
        logger.info(f"📄 [File Understanding] Extracted {len(extracted)} chars from [{safe_name}].")
        return (
            f"<ATTACHED_FILE name=\\"{safe_name}\\">\\n"
            f"{extracted}\\n"
            f"</ATTACHED_FILE>\\n"
            f"{caption_instruction}"
        )

    @classmethod
    async def _download_bot_api_file_bytes(
        cls,
        file_id: str,
        bot_token: str,
        http_client: Any,
    ) -> Optional[bytes]:
        if not file_id or not bot_token or not http_client:
            return None
        try:
            info_res = await http_client.get(
                f"https://api.telegram.org/bot{bot_token}/getFile",
                params={"file_id": file_id},
                timeout=15.0,
            )
            if info_res.status_code != 200:
                return None
            file_path_tg = info_res.json().get("result", {}).get("file_path")
            if not file_path_tg:
                return None
            dl_res = await http_client.get(
                f"https://api.telegram.org/file/bot{bot_token}/{file_path_tg}",
                timeout=25.0,
            )
            if dl_res.status_code == 200:
                return dl_res.content
        except Exception as exc:
            logger.debug(f"Bot API file download notice for [{file_id}]: {exc}")
        return None

    @classmethod
    async def inspect_bot_api_media(
        cls,
        msg: Dict[str, Any],
        bot_token: str,
        http_client: Any,
    ) -> Optional[Tuple[str, str]]:
        """
        Unified Bot API Multimodal Inspector for Master Bot and all Factory Sub-Bots.
        Inspects Stickers (.webp, .webm, .tgs), GIFs/Animations, Photos, and Files/Documents.
        Returns (enriched_message_text, media_type) or None if not a visual/document media message.
        """
        caption = msg.get("caption", "") or ""

        # 1. Sticker (.webp static, .webm video, .tgs animated)
        sticker = msg.get("sticker")
        if sticker:
            emoji = sticker.get("emoji", "") or "✨"
            is_animated = bool(sticker.get("is_animated"))  # .tgs
            is_video = bool(sticker.get("is_video"))        # .webm
            thumb_obj = sticker.get("thumbnail") or sticker.get("thumb") or {}
            thumb_file_id = thumb_obj.get("file_id")

            frames: List[Tuple[bytes, str]] = []
            if is_animated:
                # .tgs animated sticker: download thumbnail (.jpg / .webp)
                if thumb_file_id:
                    t_bytes = await cls._download_bot_api_file_bytes(thumb_file_id, bot_token, http_client)
                    if t_bytes:
                        mime = "image/webp" if t_bytes[:4] == b"RIFF" else "image/jpeg"
                        frames.append((t_bytes, mime))
            elif is_video:
                # .webm video sticker: extract keyframes via FFmpeg, fallback to thumbnail
                v_bytes = await cls._download_bot_api_file_bytes(sticker.get("file_id", ""), bot_token, http_client)
                if v_bytes:
                    frames = await cls.extract_keyframes_with_ffmpeg(v_bytes, ext=".webm", max_frames=2)
                if not frames and thumb_file_id:
                    t_bytes = await cls._download_bot_api_file_bytes(thumb_file_id, bot_token, http_client)
                    if t_bytes:
                        mime = "image/webp" if t_bytes[:4] == b"RIFF" else "image/jpeg"
                        frames.append((t_bytes, mime))
            else:
                # Static .webp sticker
                s_bytes = await cls._download_bot_api_file_bytes(sticker.get("file_id", ""), bot_token, http_client)
                if s_bytes:
                    frames.append((s_bytes, "image/webp"))

            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="sticker",
                sticker_emoji=emoji,
                user_caption=caption,
            )
            return enriched, "sticker"

        # 2. GIF / Animation
        anim = msg.get("animation")
        if anim:
            frames = []
            file_size = int(anim.get("file_size", 0) or 0)
            thumb_obj = anim.get("thumbnail") or anim.get("thumb") or {}
            thumb_id = thumb_obj.get("file_id")
            if 0 < file_size <= 6 * 1024 * 1024:
                a_bytes = await cls._download_bot_api_file_bytes(anim.get("file_id", ""), bot_token, http_client)
                if a_bytes:
                    frames = await cls.extract_keyframes_with_ffmpeg(a_bytes, ext=".mp4", max_frames=2)
            if not frames and thumb_id:
                t_bytes = await cls._download_bot_api_file_bytes(thumb_id, bot_token, http_client)
                if t_bytes:
                    frames.append((t_bytes, "image/jpeg"))
            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="gif",
                user_caption=caption,
            )
            return enriched, "sticker"

        # 3. Photo
        photos = msg.get("photo")
        if photos and isinstance(photos, list):
            best_photo = photos[-1]
            p_bytes = await cls._download_bot_api_file_bytes(best_photo.get("file_id", ""), bot_token, http_client)
            frames = [(p_bytes, "image/jpeg")] if p_bytes else []
            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="photo",
                user_caption=caption,
            )
            return enriched, "photo"

        # 4. Document / File
        doc = msg.get("document")
        if doc:
            file_name = doc.get("file_name", "") or "attached_file"
            mime_type = (doc.get("mime_type", "") or "").lower()
            file_size = int(doc.get("file_size", 0) or 0)
            _, ext = os.path.splitext(file_name.lower())

            if mime_type.startswith("image/") and file_size <= 8 * 1024 * 1024:
                d_bytes = await cls._download_bot_api_file_bytes(doc.get("file_id", ""), bot_token, http_client)
                if d_bytes:
                    enriched = await cls.analyze_visual_media_with_gemini(
                        visual_frames=[(d_bytes, mime_type)],
                        media_kind="photo",
                        user_caption=caption,
                    )
                    return enriched, "photo"

            if (ext in cls.SUPPORTED_TEXT_EXTENSIONS or mime_type.startswith("text/") or "json" in mime_type or "pdf" in mime_type) and file_size <= 10 * 1024 * 1024:
                d_bytes = await cls._download_bot_api_file_bytes(doc.get("file_id", ""), bot_token, http_client)
                if d_bytes:
                    doc_prompt = cls.extract_document_text(d_bytes, file_name, user_caption=caption)
                    if doc_prompt:
                        return doc_prompt, "document"

        return None

    @classmethod
    async def inspect_telethon_media(
        cls,
        event: Any,
    ) -> Optional[Tuple[str, str]]:
        """
        Unified Telethon MTProto Multimodal Inspector for Userbot.
        Inspects Stickers (.webp, .webm, .tgs), GIFs, Photos, and Files/Documents.
        Returns (enriched_message_text, media_type) or None.
        """
        raw_caption = getattr(event, "raw_text", "") or ""
        file_obj = getattr(event, "file", None)
        mime_type = (getattr(file_obj, "mime_type", "") or "").lower()

        # 1. Sticker
        if getattr(event, "sticker", None):
            sticker_emoji = getattr(file_obj, "emoji", "") or "✨"
            frames: List[Tuple[bytes, str]] = []
            try:
                if "x-tgsticker" in mime_type:
                    # Animated .tgs sticker -> download thumbnail image
                    t_bytes = await event.download_media(bytes, thumb=-1)
                    if t_bytes:
                        t_mime = "image/webp" if t_bytes[:4] == b"RIFF" else "image/jpeg"
                        frames.append((t_bytes, t_mime))
                elif "webm" in mime_type or "video" in mime_type:
                    # Video .webm sticker -> extract keyframes via FFmpeg, fallback to thumb
                    v_bytes = await event.download_media(bytes)
                    if v_bytes:
                        frames = await cls.extract_keyframes_with_ffmpeg(v_bytes, ext=".webm", max_frames=2)
                    if not frames:
                        t_bytes = await event.download_media(bytes, thumb=-1)
                        if t_bytes:
                            t_mime = "image/webp" if t_bytes[:4] == b"RIFF" else "image/jpeg"
                            frames.append((t_bytes, t_mime))
                else:
                    # Static .webp sticker
                    s_bytes = await event.download_media(bytes)
                    if s_bytes:
                        frames.append((s_bytes, "image/webp"))
            except Exception as st_err:
                logger.debug(f"Telethon sticker download notice: {st_err}")

            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="sticker",
                sticker_emoji=sticker_emoji,
                user_caption=raw_caption,
            )
            return enriched, "sticker"

        # 2. GIF / Animation
        if getattr(event, "gif", None):
            frames = []
            try:
                g_bytes = await event.download_media(bytes)
                if g_bytes:
                    frames = await cls.extract_keyframes_with_ffmpeg(g_bytes, ext=".mp4", max_frames=2)
                if not frames:
                    t_bytes = await event.download_media(bytes, thumb=-1)
                    if t_bytes:
                        frames.append((t_bytes, "image/jpeg"))
            except Exception as gf_err:
                logger.debug(f"Telethon GIF download notice: {gf_err}")

            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="gif",
                user_caption=raw_caption,
            )
            return enriched, "sticker"

        # 3. Photo
        if getattr(event, "photo", None):
            frames = []
            try:
                p_bytes = await event.download_media(bytes)
                if p_bytes:
                    frames.append((p_bytes, "image/jpeg"))
            except Exception as ph_err:
                logger.debug(f"Telethon photo download notice: {ph_err}")

            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="photo",
                user_caption=raw_caption,
            )
            return enriched, "photo"

        # 4. Document / File (not voice/audio/video/sticker)
        if getattr(event, "document", None) and not (getattr(event, "voice", None) or getattr(event, "audio", None)):
            file_name = getattr(file_obj, "name", "") or "attached_file.txt"
            file_size = int(getattr(file_obj, "size", 0) or 0)
            _, ext = os.path.splitext(file_name.lower())

            if mime_type.startswith("image/") and file_size <= 8 * 1024 * 1024:
                try:
                    d_bytes = await event.download_media(bytes)
                    if d_bytes:
                        enriched = await cls.analyze_visual_media_with_gemini(
                            visual_frames=[(d_bytes, mime_type)],
                            media_kind="photo",
                            user_caption=raw_caption,
                        )
                        return enriched, "photo"
                except Exception:
                    pass

            if (ext in cls.SUPPORTED_TEXT_EXTENSIONS or mime_type.startswith("text/") or "json" in mime_type or "pdf" in mime_type) and file_size <= 10 * 1024 * 1024:
                try:
                    d_bytes = await event.download_media(bytes)
                    if d_bytes:
                        doc_prompt = cls.extract_document_text(d_bytes, file_name, user_caption=raw_caption)
                        if doc_prompt:
                            return doc_prompt, "document"
                except Exception as doc_err:
                    logger.debug(f"Telethon document download notice: {doc_err}")

        return None
'''

mh = sub(mh,
"media_handler = MediaEventHandler()",
MULTIMODAL_VISION_METHODS.lstrip("\n") + "\n\nmedia_handler = MediaEventHandler()",
"media_handler: Task 3.2 multimodal vision & file extraction methods added")
ww(MEDH, mh)

# ───────────────────────── 3. mtproto_manager.py ─────────────────────────
mp = rw(MTPR)

# 3a. Master Bot API (_process_telegram_update): use media_handler.inspect_bot_api_media
mp = sub(mp,
"""        # 0. Intelligent Media & Sticker Parsing
        media_type = "text"
        sticker = msg.get("sticker")
        if sticker:
            sticker_emoji = sticker.get("emoji", "✨")
            message_text = f"[ملصق تعبيري: {sticker_emoji}]"
            media_type = "sticker"
        elif msg.get("photo"):
            media_type = "photo"
            message_text = msg.get("caption", "") or "[صورة]"
        elif msg.get("voice") or msg.get("audio"):
            media_type = "voice"
            message_text = "[رسالة صوتية]"
        else:
            message_text = msg.get("text", "") or msg.get("caption", "")""",
"""        # 0. Task 3.2: Deep Multimodal Vision & File Parsing (Stickers, GIFs, Photos, Documents)
        from aether_human_core.telegram_client.handlers.media_handler import media_handler as _mh_vis
        media_type = "text"
        if msg.get("voice") or msg.get("audio"):
            media_type = "voice"
            message_text = "[رسالة صوتية]"
        elif msg.get("sticker") or msg.get("animation") or msg.get("photo") or msg.get("document"):
            http_vis = await self._get_http()
            inspected = await _mh_vis.inspect_bot_api_media(msg, self.bot_token, http_vis)
            if inspected:
                message_text, media_type = inspected
            else:
                message_text = msg.get("text", "") or msg.get("caption", "") or "[وسائط]"
        else:
            message_text = msg.get("text", "") or msg.get("caption", "")""",
"mtproto: Master Bot API multimodal vision & file inspection")

# 3b. Telethon Userbot (on_new_message): use media_handler.inspect_telethon_media
mp = sub(mp,
"""            # Parse stickers and media in Telethon
            if getattr(event, "sticker", None):
                sticker_emoji = getattr(getattr(event, "file", None), "emoji", "") or "✨"
                msg_text = f"[ملصق تعبيري: {sticker_emoji}]"
                media_type = "sticker"
            elif getattr(event, "photo", None):
                media_type = "photo"
                msg_text = msg_text or "[صورة]"
            elif getattr(event, "voice", None) or getattr(event, "audio", None):
                media_type = "voice"
                msg_text = "[رسالة صوتية]\"""",
"""            # Task 3.2: Deep Multimodal Vision & File Parsing in Telethon Userbot
            from aether_human_core.telegram_client.handlers.media_handler import media_handler as _ub_mh_vis
            if getattr(event, "voice", None) or getattr(event, "audio", None):
                media_type = "voice"
                msg_text = "[رسالة صوتية]"
            elif getattr(event, "sticker", None) or getattr(event, "gif", None) or getattr(event, "photo", None) or getattr(event, "document", None):
                inspected_ub = await _ub_mh_vis.inspect_telethon_media(event)
                if inspected_ub:
                    msg_text, media_type = inspected_ub
                elif getattr(event, "sticker", None):
                    sticker_emoji = getattr(getattr(event, "file", None), "emoji", "") or "✨"
                    msg_text = f"[ملصق تعبيري: {sticker_emoji}]"
                    media_type = "sticker"
                elif getattr(event, "photo", None):
                    media_type = "photo"
                    msg_text = msg_text or "[صورة]\"""",
"mtproto: Telethon Userbot multimodal vision & file inspection")
ww(MTPR, mp)

# ───────────────────────── 4. multi_bot_dispatcher.py ─────────────────────────
mb = rw(MBDP)
mb = sub(mb,
"""        # Parse media
        sticker = msg.get("sticker")
        if sticker:
            emoji = sticker.get("emoji", "✨")
            text = f"[ملصق تعبيري: {emoji}]"
            media_type = "sticker"
        elif msg.get("photo"):
            text = msg.get("caption", "") or "[صورة]"
            media_type = "photo"
        elif msg.get("voice") or msg.get("audio"):""",
"""        # Task 3.2: Deep Multimodal Vision & File Parsing for Factory Sub-Bots
        from aether_human_core.telegram_client.handlers.media_handler import media_handler as _sub_mh_vis
        if msg.get("sticker") or msg.get("animation") or msg.get("photo") or msg.get("document"):
            inspected_sub = await _sub_mh_vis.inspect_bot_api_media(msg, token, http)
            if inspected_sub:
                text, media_type = inspected_sub
            else:
                text = msg.get("text", "") or msg.get("caption", "") or "[وسائط]"
                media_type = "text"
        elif msg.get("voice") or msg.get("audio"):""",
"multi_bot_dispatcher: Factory Sub-Bots multimodal vision & file inspection")
ww(MBDP, mb)

# ───────────────────────── 5. orchestrator.py ─────────────────────────
o = rw(ORCH)
o = sub(o,
"""        is_factory_persona = bool(target_bot_id and target_bot_id != "master_omar_official") or is_userbot
        if not active_rules and not has_custom_persona and not is_factory_persona:""",
"""        is_factory_persona = bool(target_bot_id and target_bot_id != "master_omar_official") or is_userbot
        is_multimodal_msg = (media_type in ("sticker", "photo", "document", "gif")) or ("<ATTACHED_FILE" in message_text)
        if not active_rules and not has_custom_persona and not is_factory_persona and not is_multimodal_msg:""",
"orchestrator: bypass heuristic cache for multimodal vision/document messages")

o = sub(o,
"""        # Technical & Programming Code Formatting Guidance""",
"""        # ── TASK 3.2: Multimodal Vision & Attached File Context Guidance ──
        if "<ATTACHED_FILE" in message_text or media_type == "document":
            special_persona_guidance += (
                "\\n\\n📄 [ملف مرفق من المستخدم - TASK 3.2]:\\n"
                "المستخدم أرسل لك ملفاً نصياً أو كوداً برمجياً داخل تاج <ATTACHED_FILE>. "
                "اقرأ محتوى الملف الفعلي بعناية، وناقشه أو صحح أخطاءه أو اشرحه للمستخدم بذكاء وبأسلوبك البشري الطبيعي."
            )
        elif media_type in ("sticker", "photo", "gif"):
            special_persona_guidance += (
                "\\n\\n👁️ [رؤية بصرية للملصق / الصورة / الـ GIF - TASK 3.2]:\\n"
                "لقد رأيت المحتوى البصري الفعلي للملصق أو الصورة المرفقة (الموصوف لك بين الأقواس). "
                "رد بتلقائية وخفة دم كإنسان شايف الصورة أو الريأكشن المرسوم في الملصق بعينه، دون أن تقول 'أنا قرأت وصف الصورة'."
            )

        # Technical & Programming Code Formatting Guidance""",
"orchestrator: Task 3.2 multimodal vision & attached file guidance")
ww(ORCH, o)

print("Done PART 3 patches.")

