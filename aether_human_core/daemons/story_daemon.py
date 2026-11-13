"""
Autonomous Telegram Stories Daemon (Project Aether-Human V4.0 - PART 3 Task 3.1).
1. 100% Guaranteed Autonomous Story Posting every 48 hours (+ mood triggers):
   - Reads Userbot Gg's current mood (Hormones) & circadian/chat context.
   - Generates an authentic 1-2 line Egyptian human status/quote via Gemini.
   - Renders a 1080x1920 vertical Story image with mood-matched dark aesthetic
     gradient/vignette + properly shaped & centered Arabic typography (Pillow + arabic_reshaper + bidi).
   - Publishes via Telethon `functions.stories.SendStoryRequest`.
2. Autonomous Story Viewer & Reactor (every 2 to 4 hours):
   - Calls `functions.stories.GetAllStoriesRequest()` to fetch active stories from contacts.
   - Marks unread stories as read (`functions.stories.ReadStoriesRequest`) after a human delay.
   - With 25%-40% probability (higher for Creator ECENN and close friends), sends a Story Reaction
     (`functions.stories.SendReactionRequest` with ❤️ or 🔥) or a short casual DM reply commenting on their story.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import re
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from aether_human_core.config.settings import settings
from aether_human_core.config.llm_router import llm_pool, sanitize_and_validate_reply
from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
from aether_human_core.psychology_engine.circadian_rhythm import circadian_engine

logger = logging.getLogger("Aether.Daemon.StoryDaemon")

# Built-in Arabic contextual glyph table (Unicode Presentation Forms-B fallback)
# Used automatically if `arabic_reshaper` / `python-bidi` are not yet loaded.
_ARABIC_GLYPH_MAP: Dict[str, Tuple[str, str, str, str]] = {
    # char: (isolated, final, initial, medial)
    "ء": ("\uFE80", "\uFE80", "\uFE80", "\uFE80"),
    "آ": ("\uFE81", "\uFE82", "\uFE81", "\uFE82"),
    "أ": ("\uFE83", "\uFE84", "\uFE83", "\uFE84"),
    "ؤ": ("\uFE85", "\uFE86", "\uFE85", "\uFE86"),
    "إ": ("\uFE87", "\uFE88", "\uFE87", "\uFE88"),
    "ئ": ("\uFE89", "\uFE8A", "\uFE8B", "\uFE8C"),
    "ا": ("\uFE8D", "\uFE8E", "\uFE8D", "\uFE8E"),
    "ب": ("\uFE8F", "\uFE90", "\uFE91", "\uFE92"),
    "ة": ("\uFE93", "\uFE94", "\uFE93", "\uFE94"),
    "ت": ("\uFE95", "\uFE96", "\uFE97", "\uFE98"),
    "ث": ("\uFE99", "\uFE9A", "\uFE9B", "\uFE9C"),
    "ج": ("\uFE9D", "\uFE9E", "\uFE9F", "\uFEA0"),
    "ح": ("\uFEA1", "\uFEA2", "\uFEA3", "\uFEA4"),
    "خ": ("\uFEA5", "\uFEA6", "\uFEA7", "\uFEA8"),
    "د": ("\uFEA9", "\uFEAA", "\uFEA9", "\uFEAA"),
    "ذ": ("\uFEAB", "\uFEAC", "\uFEAB", "\uFEAC"),
    "ر": ("\uFEAD", "\uFEAE", "\uFEAD", "\uFEAE"),
    "ز": ("\uFEAF", "\uFEB0", "\uFEAF", "\uFEB0"),
    "س": ("\uFEB1", "\uFEB2", "\uFEB3", "\uFEB4"),
    "ش": ("\uFEB5", "\uFEB6", "\uFEB7", "\uFEB8"),
    "ص": ("\uFEB9", "\uFEBA", "\uFEBB", "\uFEBC"),
    "ض": ("\uFEBD", "\uFEBE", "\uFEBF", "\uFEC0"),
    "ط": ("\uFEC1", "\uFEC2", "\uFEC3", "\uFEC4"),
    "ظ": ("\uFEC5", "\uFEC6", "\uFEC7", "\uFEC8"),
    "ع": ("\uFEC9", "\uFECA", "\uFECB", "\uFECC"),
    "غ": ("\uFECD", "\uFECE", "\uFECEF", "\uFED0"),
    "ف": ("\uFED1", "\uFED2", "\uFED3", "\uFED4"),
    "ق": ("\uFED5", "\uFED6", "\uFED7", "\uFED8"),
    "ك": ("\uFED9", "\uFEDA", "\uFEDB", "\uFEDC"),
    "ل": ("\uFEDD", "\uFEDE", "\uFEDF", "\uFEE0"),
    "م": ("\uFEE1", "\uFEE2", "\uFEE3", "\uFEE4"),
    "ن": ("\uFEE5", "\uFEE6", "\uFEE7", "\uFEE8"),
    "ه": ("\uFEE9", "\uFEEA", "\uFEEB", "\uFEEC"),
    "و": ("\uFEED", "\uFEEE", "\uFEED", "\uFEEE"),
    "ى": ("\uFEEF", "\uFEF0", "\uFEEF", "\uFEF0"),
    "ي": ("\uFEF1", "\uFEF2", "\uFEF3", "\uFEF4"),
}
_NON_CONNECTING_NEXT = {"ء", "آ", "أ", "ؤ", "إ", "ا", "ة", "د", "ذ", "ر", "ز", "و", "ى"}


def shape_arabic_text(text: str) -> str:
    """
    Shapes Arabic text into connected contextual glyphs and applies BiDi visual order
    for Pillow ImageDraw. Uses `arabic_reshaper` + `python-bidi` when available,
    and falls back to built-in Unicode Presentation Forms-B shaping.
    """
    if not text:
        return ""
    try:
        import arabic_reshaper  # type: ignore
        from bidi.algorithm import get_display  # type: ignore
        reshaped = arabic_reshaper.reshape(text)
        return str(get_display(reshaped))
    except Exception:
        # Built-in pure-Python Arabic contextual shaper + RTL visual reversal
        words = text.split(" ")
        shaped_words: List[str] = []
        for word in words:
            if not any(ch in _ARABIC_GLYPH_MAP for ch in word):
                shaped_words.append(word)
                continue
            chars = list(word)
            out: List[str] = []
            n = len(chars)
            for idx, ch in enumerate(chars):
                if ch not in _ARABIC_GLYPH_MAP:
                    out.append(ch)
                    continue
                prev_ch = chars[idx - 1] if idx > 0 else ""
                next_ch = chars[idx + 1] if idx + 1 < n else ""
                connects_prev = (prev_ch in _ARABIC_GLYPH_MAP) and (prev_ch not in _NON_CONNECTING_NEXT)
                connects_next = (next_ch in _ARABIC_GLYPH_MAP) and (ch not in _NON_CONNECTING_NEXT)
                iso, fin, ini, med = _ARABIC_GLYPH_MAP[ch]
                if connects_prev and connects_next:
                    out.append(med)
                elif connects_prev and not connects_next:
                    out.append(fin)
                elif not connects_prev and connects_next:
                    out.append(ini)
                else:
                    out.append(iso)
            shaped_words.append("".join(reversed(out)))
        return " ".join(reversed(shaped_words))


class TelegramStoryDaemon:
    """
    Autonomous Telegram Stories Poster (guaranteed <=48h interval) and Friends' Story Viewer/Reactor.
    """

    STORY_INTERVAL_SECONDS: float = 48.0 * 3600.0  # 48 hours hard guarantee
    CHECK_POST_LOOP_SECONDS: float = 3600.0        # Check every 1 hour

    # Mood palettes for 1080x1920 vertical story canvas:
    # (top_rgb, mid_rgb, bottom_rgb, accent_rgb, mood_label_ar)
    MOOD_THEMES: Dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], str]] = {
        "dark_melancholic": (
            (11, 13, 23),
            (22, 26, 46),
            (8, 9, 15),
            (130, 148, 196),
            "هدوء آخر الليل",
        ),
        "cyberpunk_coding": (
            (9, 18, 28),
            (16, 39, 58),
            (7, 11, 20),
            (0, 229, 255),
            "سهرة كود وتفكير",
        ),
        "sarcastic_sharp": (
            (26, 13, 24),
            (52, 21, 43),
            (14, 7, 14),
            (255, 107, 157),
            "كلام على بلاطة",
        ),
        "chill_coffee": (
            (24, 18, 16),
            (48, 34, 28),
            (15, 11, 9),
            (235, 185, 130),
            "روقان وقهوة",
        ),
        "happy_energetic": (
            (14, 22, 38),
            (28, 49, 82),
            (10, 14, 26),
            (110, 231, 183),
            "مزاج رايق",
        ),
    }

    FALLBACK_MOOD_QUOTES: Dict[str, List[str]] = {
        "dark_melancholic": [
            "أكتر وقت بتفهم فيه الدنيا صح هو لما تقعد لوحدك في هدوء الليل وتراجع حساباتك",
            "مش كل اللي ساكت مرتاح ساعات السكوت بيبقى زحمة كلام ملوش لازمة يتقال",
            "اللي يشتري خاطرك في عز زحمته غير اللي يفتكرك بس لما يفضى",
        ],
        "cyberpunk_coding": [
            "الناس نايمة وأنا لسه بدور على الباج اللي موقف السيرفر من ساعتين بس برضه هجيبه",
            "مفيش أحلى من سهرة الكود والقهوة لما الدنيا كلها تهدى والترمينال بس اللي منور",
            "الكود النظيف زي الصاحب الجدع مبيخذلكش وقت الزنقة",
        ],
        "sarcastic_sharp": [
            "بعض الناس محتاجين يعملوا ريستارت لدماغهم قبل ما يتكلموا الصبح",
            "بقينا في زمن الكل فيه فاهم كل حاجة وهو مش عارف يظبط يومه أصلا",
            "عامل الناس بنفس طريقتهم وهتشوف إزاي هيزعلوا من تصرفاتهم",
        ],
        "chill_coffee": [
            "كوباية القهوة وشوية هدوء كفيلين يصلحوا أي يوم ملخبط",
            "خليك تقيل ورايق كده مفيش حاجة مستاهلة تحرق أعصابك عشانها",
            "أحلى حاجة لما تبقى في حالك ومش شاغل بالك غير بروقانك وبس",
        ],
        "happy_energetic": [
            "الحمد لله على الناس السالكة اللي وجودها بيخلي اليوم أخف وأحلى",
            "يوم رايق من أوله والواحد فايق ومستعد لأي أكشن النهاردة",
            "الضحكة الحلوة مع الناس الصح بتغني عن الدنيا وما فيها",
        ],
    }

    def __init__(self) -> None:
        self.state_dir = os.path.join(os.getcwd(), "artifacts", "stories")
        os.makedirs(self.state_dir, exist_ok=True)
        self.state_file = os.path.join(self.state_dir, "story_daemon_state.json")
        self._is_running: bool = False
        self._poster_task: Optional[asyncio.Task] = None
        self._viewer_task: Optional[asyncio.Task] = None
        self._viewer_tracker_task: Optional[asyncio.Task] = None
        self._state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        default_state: Dict[str, Any] = {
            "last_story_timestamp": 0.0,
            "last_story_caption": "",
            "last_story_mood": "",
            "total_stories_posted": 0,
            "reacted_stories": {},  # peer_id_str -> list of story_ids
        }
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    default_state.update(loaded)
            except Exception as exc:
                logger.warning(f"StoryDaemon: Could not load state file ({exc}), using defaults.")
        return default_state

    def _save_state(self) -> None:
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning(f"StoryDaemon: Failed to persist state file: {exc}")

    def _get_userbot_client(self) -> Optional[Any]:
        from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
        if mtproto_manager.client and mtproto_manager.client.is_connected():
            return mtproto_manager.client
        try:
            from bot_factory.interactive_userbot_auth import interactive_userbot
            if interactive_userbot.client and interactive_userbot.client.is_connected():
                return interactive_userbot.client
        except Exception:
            pass
        return None

    def start(self) -> None:
        if not self._is_running:
            self._is_running = True
            self._poster_task = asyncio.create_task(self._story_poster_loop())
            self._viewer_task = asyncio.create_task(self._story_viewer_loop())
            self._viewer_tracker_task = asyncio.create_task(self._viewer_tracker_loop())
            logger.info("📸 Autonomous Telegram Story Daemon (48h Poster + Mood Music + Story Viewers Tracker) started.")

    def stop(self) -> None:
        self._is_running = False
        for t in (self._poster_task, self._viewer_task, self._viewer_tracker_task):
            if t and not t.done():
                t.cancel()
        logger.info("Autonomous Telegram Story Daemon stopped.")

    def resolve_current_mood_key(self) -> str:
        """
        Maps Userbot's current neuro-hormones and circadian hour to a Story aesthetic mood theme.
        """
        h = endocrine_engine.get_current_state()
        circadian = circadian_engine.evaluate_circadian_state()
        hour = int(circadian.get("hour", datetime.now().hour))

        if h.cortisol > 0.62:
            return "sarcastic_sharp"
        if h.serotonin < 0.42 or (1 <= hour <= 5 and h.oxytocin < 0.55):
            return "dark_melancholic"
        if 22 <= hour or hour <= 3:
            return "cyberpunk_coding"
        if h.dopamine > 0.70:
            return "happy_energetic"
        return "chill_coffee"

    async def generate_story_quote(self, mood_key: str, persona_name: str = "ريمي") -> str:
        """
        Prompts Gemini to craft an authentic 1-2 line Egyptian human story quote matching mood_key.
        Falls back to curated mood quotes if API pool is busy.
        """
        _, _, _, _, mood_label_ar = self.MOOD_THEMES.get(mood_key, self.MOOD_THEMES["chill_coffee"])
        h = endocrine_engine.get_current_state()

        prompt = (
            f"أنت '{persona_name}' تنشر ستوري (حالة تليجرام) شخصية على حسابك الآن.\n"
            f"حالتك المزاجية الحالية: {mood_label_ar} "
            f"(دوبامين={h.dopamine:.2f} كورتيزول={h.cortisol:.2f} سيروتونين={h.serotonin:.2f}).\n"
            f"اكتب جملة ستوري بشرية حقيقية وعميقة أو ساخرة أو رايقة من سطر أو سطرين فقط (8 إلى 18 كلمة) "
            f"بالعامية المصرية الشبابية الطبيعية (سواء عن السهر أو الكود أو الدنيا أو المزاج أو الناس).\n"
            f"ممنوع الفواصل (، أو ,) وممنوع الهاشتاجات وممنوع مقدمات.. اكتب نص الستوري فقط:"
        )
        sys_inst = (
            f"أنت {persona_name} تنشر ستوري تليجرام حقيقية كإنسان طبيعي. "
            f"اكتب نصاً قصيراً جذاباً بصوتك البشري بدون أي فواصل أو علامات تنصيص."
        )
        try:
            raw = await llm_pool.generate_content(
                prompt=prompt,
                system_instruction=sys_inst,
                temperature=0.8,
            )
            cleaned = sanitize_and_validate_reply(raw)
            cleaned = re.sub(r"[\"'`«»#،,;؛]", "", cleaned).strip()
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if 12 <= len(cleaned) <= 180:
                return cleaned
        except Exception as exc:
            logger.debug(f"StoryDaemon Gemini quote fallback ({exc}).")

        quotes = self.FALLBACK_MOOD_QUOTES.get(mood_key, self.FALLBACK_MOOD_QUOTES["chill_coffee"])
        return random.choice(quotes)

    def render_story_image(
        self,
        quote_text: str,
        mood_key: str = "chill_coffee",
        persona_name: str = "Gg",
        output_path: Optional[str] = None,
        song_sticker: Optional[str] = None,
    ) -> str:
        """
        Dynamically generates a high-resolution 1080x1920 vertical Telegram Story image
        with mood gradient, ambient bokeh/cyberpunk glow, dark vignette, and centered
        Arabic typography.
        """
        width, height = 1080, 1920
        top_c, mid_c, bot_c, accent_c, mood_label_ar = self.MOOD_THEMES.get(
            mood_key, self.MOOD_THEMES["chill_coffee"]
        )

        img = Image.new("RGB", (width, height), bot_c)
        draw = ImageDraw.Draw(img)

        # 1. Smooth 3-stop vertical gradient background
        half_h = height // 2
        for y in range(height):
            if y < half_h:
                t = y / float(half_h)
                r = int(top_c[0] * (1 - t) + mid_c[0] * t)
                g = int(top_c[1] * (1 - t) + mid_c[1] * t)
                b = int(top_c[2] * (1 - t) + mid_c[2] * t)
            else:
                t = (y - half_h) / float(height - half_h)
                r = int(mid_c[0] * (1 - t) + bot_c[0] * t)
                g = int(mid_c[1] * (1 - t) + bot_c[1] * t)
                b = int(mid_c[2] * (1 - t) + bot_c[2] * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # 2. Atmospheric glow orbs + soft blur
        glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(glow_layer)
        for _ in range(7):
            cx = random.randint(140, width - 140)
            cy = random.randint(250, height - 250)
            rad = random.randint(140, 340)
            alpha = random.randint(22, 48)
            g_draw.ellipse(
                [cx - rad, cy - rad, cx + rad, cy + rad],
                fill=(accent_c[0], accent_c[1], accent_c[2], alpha),
            )
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=65))
        img = Image.alpha_composite(img.convert("RGBA"), glow_layer).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 3. Sleek central glassmorphism card frame
        card_margin_x = 90
        card_top = 560
        card_bottom = 1360
        card_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(card_layer)
        c_draw.rounded_rectangle(
            [card_margin_x, card_top, width - card_margin_x, card_bottom],
            radius=42,
            fill=(10, 12, 20, 145),
            outline=(accent_c[0], accent_c[1], accent_c[2], 120),
            width=3,
        )
        # Accent top bar inside card
        c_draw.rounded_rectangle(
            [width // 2 - 90, card_top + 48, width // 2 + 90, card_top + 56],
            radius=4,
            fill=(accent_c[0], accent_c[1], accent_c[2], 210),
        )
        img = Image.alpha_composite(img.convert("RGBA"), card_layer).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 4. Load Arabic-capable TrueType font
        font_candidates = [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\tahoma.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]
        main_font = None
        sub_font = None
        for fp in font_candidates:
            if os.path.exists(fp):
                try:
                    main_font = ImageFont.truetype(fp, 54)
                    sub_font = ImageFont.truetype(fp, 34)
                    break
                except Exception:
                    continue
        if main_font is None:
            main_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()

        # 5. Word-wrap Arabic quote into balanced lines (4 to 5 words per line)
        words = quote_text.strip().split()
        raw_lines: List[str] = []
        chunk_size = 4 if len(words) <= 12 else 5
        for i in range(0, len(words), chunk_size):
            raw_lines.append(" ".join(words[i : i + chunk_size]))
        raw_lines = raw_lines[:5]

        line_spacing = 88
        total_text_h = len(raw_lines) * line_spacing
        start_y = ((card_top + card_bottom) // 2) - (total_text_h // 2) + 10

        for idx, raw_line in enumerate(raw_lines):
            shaped_line = shape_arabic_text(raw_line)
            try:
                bbox = draw.textbbox((0, 0), shaped_line, font=main_font)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(shaped_line) * 24
            tx = (width - tw) // 2
            ty = start_y + idx * line_spacing
            # Soft shadow
            draw.text((tx + 3, ty + 3), shaped_line, font=main_font, fill=(0, 0, 0))
            # Crisp main text
            draw.text((tx, ty), shaped_line, font=main_font, fill=(245, 247, 252))

        # 5b. Music Sticker Pill Badge (Telegram/Instagram style)
        if song_sticker:
            try:
                badge_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                b_draw = ImageDraw.Draw(badge_layer)
                badge_font = sub_font
                shaped_song = shape_arabic_text(song_sticker)
                try:
                    sbbox = draw.textbbox((0, 0), shaped_song, font=badge_font)
                    sw = sbbox[2] - sbbox[0]
                    sh = sbbox[3] - sbbox[1]
                except Exception:
                    sw = len(shaped_song) * 16
                    sh = 28
                badge_w = sw + 56
                badge_h = 52
                badge_x = (width - badge_w) // 2
                badge_y = card_top + 78
                b_draw.rounded_rectangle(
                    [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
                    radius=26,
                    fill=(16, 20, 32, 190),
                    outline=(accent_c[0], accent_c[1], accent_c[2], 150),
                    width=2,
                )
                b_draw.text(
                    (badge_x + 28, badge_y + (badge_h - sh) // 2 - 2),
                    shaped_song,
                    font=badge_font,
                    fill=(240, 245, 255, 245),
                )
                img = Image.alpha_composite(img.convert("RGBA"), badge_layer).convert("RGB")
                draw = ImageDraw.Draw(img)
            except Exception as b_err:
                logger.debug(f"Music sticker badge render notice: {b_err}")

        # 6. Footer mood label & timestamp
        now_str = datetime.now().strftime("%I:%M %p")
        footer_raw = f"{mood_label_ar}  •  {now_str}"
        footer_shaped = shape_arabic_text(footer_raw)
        try:
            fbbox = draw.textbbox((0, 0), footer_shaped, font=sub_font)
            fw = fbbox[2] - fbbox[0]
        except Exception:
            fw = len(footer_shaped) * 16
        draw.text(
            ((width - fw) // 2, card_bottom - 85),
            footer_shaped,
            font=sub_font,
            fill=accent_c,
        )

        if not output_path:
            output_path = os.path.join(self.state_dir, f"story_{int(time.time())}.jpg")
        img.save(output_path, "JPEG", quality=93)
        logger.info(f"🎨 Rendered 1080x1920 Story image at [{output_path}] (mood={mood_key}).")
        return output_path

    async def publish_new_story(self, force: bool = False) -> Tuple[bool, str]:
        """
        Generates and publishes a new Telegram Story from the Userbot account via
        `functions.stories.SendStoryRequest`.
        """
        client = self._get_userbot_client()
        if not client:
            return False, "Userbot Telethon client is not connected yet."

        now = time.time()
        last_ts = float(self._state.get("last_story_timestamp", 0.0) or 0.0)
        if not force and last_ts > 0 and (now - last_ts) < self.STORY_INTERVAL_SECONDS:
            remaining_h = (self.STORY_INTERVAL_SECONDS - (now - last_ts)) / 3600.0
            return False, f"Next story scheduled in {remaining_h:.1f}h."

        try:
            me = await client.get_me()
            persona_name = getattr(me, "first_name", "ريمي") or "ريمي"
        except Exception:
            persona_name = "ريمي"

        mood_key = self.resolve_current_mood_key()
        quote = await self.generate_story_quote(mood_key=mood_key, persona_name=persona_name)

        from telethon import functions, types
        from aether_human_core.multimodal_engine.acoustic_voice.story_song_manager import story_song_manager

        try:
            # 1. Retrieve authentic vocal song track with singing/vocals matching mood
            song_data = await story_song_manager.get_story_song(mood_key=mood_key)
            song_mp3 = song_data.get("audio_path", "")
            song_sticker = song_data.get("display_sticker", "")

            # 2. Render 1080x1920 Story image with Music Sticker
            image_path = self.render_story_image(
                quote_text=quote,
                mood_key=mood_key,
                persona_name=persona_name,
                song_sticker=song_sticker,
            )

            # 3. Render 20-second vertical MP4 video story with the vocal song track
            video_path = os.path.join(self.state_dir, f"story_video_{int(time.time())}.mp4")
            cmd = [
                "ffmpeg", "-y", "-loop", "1", "-i", image_path,
                "-i", song_mp3,
                "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
                "-shortest", "-t", "20", video_path,
            ]
            has_video = False
            try:
                await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if os.path.exists(video_path) and os.path.getsize(video_path) > 20000:
                    has_video = True
            except Exception as ffmpeg_err:
                logger.warning(f"FFmpeg story video rendering notice: {ffmpeg_err}")

            if has_video:
                uploaded_file = await client.upload_file(video_path)
                story_media = types.InputMediaUploadedDocument(
                    file=uploaded_file,
                    mime_type="video/mp4",
                    attributes=[
                        types.DocumentAttributeVideo(
                            duration=20,
                            w=1080,
                            h=1920,
                            supports_streaming=True,
                        )
                    ],
                )
            else:
                uploaded_file = await client.upload_file(image_path)
                story_media = types.InputMediaUploadedPhoto(file=uploaded_file)

            # 4. Publish story with pinned=True (guarantees story stays active in My Stories on profile and never archived away)
            res = await client(
                functions.stories.SendStoryRequest(
                    peer="me",
                    media=story_media,
                    caption=quote,
                    privacy_rules=[types.InputPrivacyValueAllowAll()],
                    period=172800,  # 48 hours
                    pinned=True,    # Highlighted in Profile story list!
                )
            )

            # Extract published story ID for viewer and reaction tracking
            published_story_id = 0
            if hasattr(res, "updates"):
                for upd in res.updates:
                    if hasattr(upd, "story") and hasattr(upd.story, "id"):
                        published_story_id = upd.story.id
                        break
            if not published_story_id and hasattr(res, "id"):
                published_story_id = res.id

            self._state["active_story_id"] = published_story_id
            self._state["last_story_timestamp"] = time.time()
            self._state["last_story_caption"] = quote
            self._state["last_story_mood"] = mood_key
            self._state["last_story_song"] = song_sticker
            self._state["last_story_video"] = video_path if has_video else image_path
            self._state["total_stories_posted"] = int(self._state.get("total_stories_posted", 0)) + 1
            self._save_state()

            logger.info(
                f"🌟 [Telegram Story Published] ID={published_story_id} | Mood={mood_key} | "
                f"Song={song_sticker or os.path.basename(song_mp3)} | Pinned=True (Never Hidden/Archived) | Caption: '{quote}'"
            )
            return True, quote
        except Exception as exc:
            # Record timestamp attempt with a 6-hour retry backoff if Telegram account restricts stories
            logger.warning(f"SendStoryRequest notice ({exc}). Backing off retry for 6h.")
            self._state["last_story_timestamp"] = time.time() - (self.STORY_INTERVAL_SECONDS - 6 * 3600.0)
            self._save_state()
            return False, str(exc)

    async def view_and_react_to_friends_stories(self) -> int:
        """
        Task 3.1 (2) — Autonomous Story Viewer & Reactor:
        Calls `functions.stories.GetAllStoriesRequest()` to fetch active stories from contacts.
        Marks unread stories as read (`ReadStoriesRequest`), and with 25%-40% probability
        (higher for Creator ECENN KING_USER_ID and close friends) sends a Story Reaction (❤️ / 🔥)
        or a short casual DM comment.
        """
        client = self._get_userbot_client()
        if not client:
            return 0

        from telethon import functions, types

        try:
            me = await client.get_me()
            my_id = getattr(me, "id", 0)
        except Exception:
            my_id = 0

        try:
            all_stories_res = await client(functions.stories.GetAllStoriesRequest(next=False, hidden=False))
        except Exception as exc:
            logger.debug(f"GetAllStoriesRequest notice: {exc}")
            return 0

        peer_stories_list = getattr(all_stories_res, "peer_stories", []) or []
        if not peer_stories_list:
            return 0

        reacted_map: Dict[str, List[int]] = self._state.get("reacted_stories", {}) or {}
        viewed_count = 0

        for ps in peer_stories_list:
            peer_obj = getattr(ps, "peer", None)
            peer_id = getattr(peer_obj, "user_id", None) or getattr(peer_obj, "channel_id", None) or 0
            if not peer_id or peer_id == my_id:
                continue

            stories = getattr(ps, "stories", []) or []
            if not stories:
                continue

            max_read_id = getattr(ps, "max_read_id", 0) or 0
            story_ids = [getattr(s, "id", 0) for s in stories if getattr(s, "id", 0) > 0]
            if not story_ids:
                continue

            max_story_id = max(story_ids)
            peer_key = str(peer_id)
            already_seen_ids = set(reacted_map.get(peer_key, []))

            unread_stories = [
                s for s in stories
                if getattr(s, "id", 0) > max_read_id and getattr(s, "id", 0) not in already_seen_ids
            ]
            if not unread_stories:
                continue

            # Wait realistic human viewing delay before marking read
            await asyncio.sleep(random.uniform(2.5, 6.5))

            try:
                input_peer = await client.get_input_entity(peer_id)
            except Exception:
                continue

            # 1. Mark stories as read
            try:
                await client(functions.stories.ReadStoriesRequest(peer=input_peer, max_id=max_story_id))
                viewed_count += len(unread_stories)
                logger.info(f"👁️ [Story Viewer] Marked {len(unread_stories)} stories as read for peer [{peer_id}] (max_id={max_story_id}).")
            except Exception as r_err:
                logger.debug(f"ReadStoriesRequest notice for peer [{peer_id}]: {r_err}")

            # Track seen story IDs
            already_seen_ids.update(getattr(s, "id", 0) for s in unread_stories)
            reacted_map[peer_key] = sorted(list(already_seen_ids))[-30:]

            # 2. Decide whether to react (25%-40% base, 85% for Creator ECENN KING_USER_ID)
            is_creator = (peer_id == settings.the_king_user_id or peer_id in settings.super_admin_ids_list)
            react_prob = 0.85 if is_creator else random.uniform(0.25, 0.40)

            target_story = unread_stories[-1]
            target_story_id = getattr(target_story, "id", max_story_id)
            story_caption = getattr(target_story, "caption", "") or ""

            if random.random() < react_prob:
                chosen_emoji = random.choice(["❤️", "🔥"])
                await asyncio.sleep(random.uniform(1.2, 3.0))
                try:
                    await client(
                        functions.stories.SendReactionRequest(
                            peer=input_peer,
                            story_id=target_story_id,
                            reaction=types.ReactionEmoji(emoticon=chosen_emoji),
                            add_to_recent=True,
                        )
                    )
                    logger.info(f"❤️ [Story Reactor] Reacted with {chosen_emoji} to story [{target_story_id}] of peer [{peer_id}].")
                except Exception as react_err:
                    logger.debug(f"Story SendReactionRequest notice for [{peer_id}]: {react_err}")

                # Optional short DM comment on story for Creator or captioned stories (20% roll)
                if (is_creator or story_caption) and random.random() < (0.35 if is_creator else 0.15):
                    try:
                        dm_comments = [
                            "الستوري رايقة أوي على فكرة 🔥",
                            "إيه الروقان ده ستوري جامدة ❤️",
                            "منور في الستوري والله ✨",
                        ]
                        comment_txt = random.choice(dm_comments)
                        await asyncio.sleep(random.uniform(2.0, 5.0))
                        await client.send_message(input_peer, comment_txt)
                        logger.info(f"💬 [Story Reactor] Sent casual story DM comment to [{peer_id}]: '{comment_txt}'")
                    except Exception:
                        pass

        self._state["reacted_stories"] = reacted_map
        self._save_state()
        return viewed_count

    async def _story_poster_loop(self) -> None:
        # Initial wait for Telethon client to finish connecting on boot
        await asyncio.sleep(25.0)
        while self._is_running:
            try:
                now = time.time()
                last_ts = float(self._state.get("last_story_timestamp", 0.0) or 0.0)
                if (now - last_ts) >= self.STORY_INTERVAL_SECONDS:
                    logger.info("⏰ 48+ hours elapsed since last Telegram Story. Triggering guaranteed autonomous Story post...")
                    await self.publish_new_story(force=True)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in StoryDaemon poster loop: {exc}")

            await asyncio.sleep(self.CHECK_POST_LOOP_SECONDS)

    async def _story_viewer_loop(self) -> None:
        # Initial wait on startup before first story viewing pass
        await asyncio.sleep(45.0)
        while self._is_running:
            try:
                circadian = circadian_engine.evaluate_circadian_state()
                if not circadian.get("is_sleeping", False):
                    await self.view_and_react_to_friends_stories()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in StoryDaemon viewer loop: {exc}")

            # Every 2 to 4 hours
            await asyncio.sleep(random.uniform(2.0 * 3600.0, 4.0 * 3600.0))



    async def check_and_report_story_viewers(self) -> int:
        """
        Fetches viewers and reactions for the active published story:
        - Stores all viewers in local state and artifacts/stories/story_viewers.json.
        - Detects new viewers and newly added reactions (e.g. ❤️, 🔥 vs view-only).
        - Sends real-time notification alert to King/Owner (the King) in private DM!
        """
        client = self._get_userbot_client()
        if not client:
            return 0

        from telethon import functions, types

        story_id = self._state.get("active_story_id", 0)
        if not story_id:
            # Attempt to discover latest active story
            try:
                my_stories = await client(functions.stories.GetPeerStoriesRequest(peer="me"))
                stories_list = getattr(getattr(my_stories, "stories", None), "stories", []) or []
                if stories_list:
                    story_id = max(getattr(s, "id", 0) for s in stories_list if getattr(s, "id", 0) > 0)
                    self._state["active_story_id"] = story_id
                    self._save_state()
            except Exception as e:
                logger.debug(f"Notice fetching my active stories: {e}")

        if not story_id:
            return 0

        try:
            views_res = await client(
                functions.stories.GetStoryViewsListRequest(
                    peer="me",
                    id=story_id,
                    offset="",
                    limit=100,
                )
            )
        except Exception as exc:
            logger.debug(f"GetStoryViewsListRequest notice for story [{story_id}]: {exc}")
            return 0

        users_map = {u.id: u for u in getattr(views_res, "users", [])}
        views_list = getattr(views_res, "views", []) or []

        notified_map = self._state.setdefault("notified_viewers", {})
        new_notifications_count = 0

        viewers_registry_file = os.path.join(self.state_dir, "story_viewers.json")
        viewers_db: Dict[str, Any] = {}
        if os.path.exists(viewers_registry_file):
            try:
                with open(viewers_registry_file, "r", encoding="utf-8") as f:
                    viewers_db = json.load(f)
            except Exception:
                viewers_db = {}

        for v in views_list:
            user_id = getattr(v, "user_id", 0)
            if not user_id:
                continue

            user_obj = users_map.get(user_id)
            first_name = getattr(user_obj, "first_name", "") or ""
            last_name = getattr(user_obj, "last_name", "") or ""
            full_name = f"{first_name} {last_name}".strip() or f"مستخدم {user_id}"
            username = getattr(user_obj, "username", "") or ""
            user_tag = f"@{username}" if username else "بدون معرف"

            # Check reaction
            reaction = getattr(v, "reaction", None)
            if reaction:
                emoticon = getattr(reaction, "emoticon", "❤️")
                reaction_label = f"✨ تفاعل بـ: {emoticon}"
                has_reaction = True
                reaction_val = emoticon
            else:
                reaction_label = "👁️ مشاهدة فقط (بدون تفاعل)"
                has_reaction = False
                reaction_val = None

            viewer_key = f"{story_id}_{user_id}"
            already_notified = notified_map.get(viewer_key)

            # Check if viewer is new OR has upgraded from view-only to an active reaction
            should_notify = False
            if not already_notified:
                should_notify = True
            elif not already_notified.get("has_reaction") and has_reaction:
                should_notify = True

            # Save / update in persistent registry
            viewers_db[viewer_key] = {
                "story_id": story_id,
                "user_id": user_id,
                "name": full_name,
                "username": username,
                "has_reaction": has_reaction,
                "reaction": reaction_val,
                "first_seen": already_notified.get("first_seen", time.time()) if already_notified else time.time(),
                "last_updated": time.time(),
            }

            if should_notify:
                notified_map[viewer_key] = {
                    "has_reaction": has_reaction,
                    "reaction": reaction_val,
                    "first_seen": viewers_db[viewer_key]["first_seen"],
                    "notified_at": time.time(),
                }
                new_notifications_count += 1

                # Send direct private DM alert to The King / Owner
                time_str = datetime.now().strftime("%I:%M %p")
                dm_alert = (
                    f"👁️ <b>[ تقرير مشاهدة وتفاعل جديد على الستوري 📸 ]</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>الاسم:</b> {full_name}\n"
                    f"🆔 <b>الآيدي:</b> <code>{user_id}</code>\n"
                    f"🔗 <b>المعرف:</b> {user_tag}\n"
                    f"⚡ <b>الحالة:</b> {reaction_label}\n"
                    f"🕒 <b>التوقيت:</b> <code>{time_str}</code>"
                )
                try:
                    target_king = settings.the_king_user_id
                    await client.send_message(target_king, dm_alert, parse_mode="html")
                    logger.info(f"📩 [Story Viewer Alert Sent to King] Viewer [{full_name} ({user_id})] | Reaction={reaction_val}")
                except Exception as send_err:
                    logger.warning(f"Failed to send story viewer DM alert to King: {send_err}")

        # Persist viewers database
        try:
            with open(viewers_registry_file, "w", encoding="utf-8") as f:
                json.dump(viewers_db, f, ensure_ascii=False, indent=2)
            self._state["notified_viewers"] = notified_map
            self._save_state()
        except Exception as save_err:
            logger.debug(f"Error saving story viewers DB: {save_err}")

        return new_notifications_count

    async def _viewer_tracker_loop(self) -> None:
        """Periodically checks for new story viewers and reactions every 12 minutes."""
        await asyncio.sleep(60.0)
        while self._is_running:
            try:
                await self.check_and_report_story_viewers()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in StoryDaemon viewer tracker loop: {exc}")

            await asyncio.sleep(random.uniform(10.0 * 60.0, 15.0 * 60.0))


story_daemon = TelegramStoryDaemon()

