"""
Human UX & Typing Simulation Engine for Project Aether-Human.
Implements Multi-Bubble message bursting, typing latency (WPM),
and realistic Arabic keyboard typo generation with automated *self-correction.
"""

from __future__ import annotations

import logging
import random
import re
import asyncio
from typing import List, Tuple, Optional
from pydantic import BaseModel

from aether_human_core.config.settings import settings
from aether_human_core.psychology_engine.circadian_rhythm import circadian_engine

logger = logging.getLogger("Aether.Telegram.HumanTyper")


class BurstMessage(BaseModel):
    text: str
    typing_delay_sec: float
    has_typo: bool = False
    correction_text: Optional[str] = None


class HumanTyperSimulator:
    """
    Transforms single text blocks into realistic human chat bursts with timing and typos.
    """
    # Common Arabic keyboard adjacent letter substitution map
    ARABIC_KEYBOARD_NEIGHBORS = {
        "ب": ["ي", "ل", "س"],
        "ي": ["ب", "س", "ش"],
        "ت": ["ن", "ا", "ك"],
        "ن": ["ت", "م", "ه"],
        "م": ["ن", "ك", "و"],
        "ك": ["م", "ت", "ط"],
        "ل": ["ب", "ا", "س"],
        "ا": ["ل", "ت", "أ"],
        "س": ["ي", "ب", "ش"],
        "ش": ["س", "ي"],
        "ر": ["ز", "د", "و"],
        "و": ["ر", "ز", "م"],
        "ه": ["ع", "خ", "ن"],
        "ع": ["ه", "غ"],
    }

    @classmethod
    def split_into_multi_bubble_bursts(
        cls,
        text: str,
        is_group: bool = False,
        max_bubbles: int = 3,
    ) -> List[str]:
        """
        Splits text into at most 2 to 3 colloquial message bubbles in private DMs,
        and returns a single unified message in groups or for long scientific/math explanations.
        Prevents Telegram 429 Too Many Requests.
        """
        cleaned = text.strip()
        if not cleaned:
            return []

        # Remove stilted Arabic & English commas for authentic colloquial texting
        cleaned_no_commas = re.sub(r"[،,؛]", "", cleaned)

        # 1. In groups, ALWAYS return a single consolidated message to avoid chat spam and 429 bans!
        if is_group:
            return [cleaned_no_commas]

        # 2. Check for mathematical, scientific, or code explanations (>350 chars or formulas/code)
        is_math_or_code = bool(
            re.search(r"(\$\$|\$|\\frac|\\sqrt|\\sum|\b[a-zA-Z]\s*=\s*|```|\bdef\b|\bimport\b)", cleaned)
        )
        if len(cleaned_no_commas) > 350 or is_math_or_code:
            # Split only on major paragraph breaks, never fragment mathematical reasoning
            paragraphs = [p.strip() for p in cleaned_no_commas.split("\n\n") if p.strip()]
            if len(paragraphs) <= 1:
                return [cleaned_no_commas]
            elif len(paragraphs) == 2:
                return paragraphs
            else:
                # Merge into 2 to 3 chunks max
                chunk_1 = paragraphs[0]
                chunk_2 = "\n\n".join(paragraphs[1: len(paragraphs)//2 + 1])
                chunk_3 = "\n\n".join(paragraphs[len(paragraphs)//2 + 1:])
                res = [c for c in [chunk_1, chunk_2, chunk_3] if c.strip()]
                return res[:max_bubbles]

        # 3. Colloquial conversational chat in private DM: max 2 to 3 short bubbles
        raw_parts = [p.strip() for p in re.split(r"[\n\r]+|\. +", cleaned_no_commas) if p.strip()]
        if len(raw_parts) <= 1:
            words = cleaned_no_commas.split()
            if len(words) > 20:
                mid = len(words) // 2
                return [" ".join(words[:mid]), " ".join(words[mid:])]
            return [cleaned_no_commas]

        bubbles: List[str] = []
        current_bubble = ""
        for part in raw_parts:
            if len(current_bubble) + len(part) < 180 and current_bubble:
                current_bubble = f"{current_bubble} {part}"
            else:
                if current_bubble:
                    bubbles.append(current_bubble.strip())
                current_bubble = part

        if current_bubble:
            bubbles.append(current_bubble.strip())

        # Strictly enforce maximum 2-3 bubbles in private chat
        if len(bubbles) > max_bubbles:
            merged = []
            slice_size = (len(bubbles) + max_bubbles - 1) // max_bubbles
            for i in range(0, len(bubbles), slice_size):
                merged.append(" ".join(bubbles[i: i + slice_size]))
            return merged[:max_bubbles]

        return bubbles if bubbles else [cleaned_no_commas]

    @classmethod
    def calculate_typing_delay(
        cls,
        text: str,
        wpm_base: int = 160,
        is_shy: bool = False,
        is_userbot: bool = False,
    ) -> float:
        """
        Calculates human typing duration.
        For Userbot: realistic human speed (~3.5 to 5.0 characters per second).
        For Official Bots: responsive typing duration.
        """
        if is_userbot:
            cps = random.uniform(3.5, 5.0)
            char_len = max(1, len(text))
            total_delay = max(1.5, min(24.0, char_len / cps))
            if is_shy:
                total_delay = min(25.0, total_delay + 1.2)
            return round(total_delay, 2)

        word_count = max(1, len(text.split()))
        jitter = random.uniform(0.3, 0.6)
        total_delay = max(0.4, min(1.5, (word_count * 0.05) + jitter))
        if is_shy:
            total_delay = min(1.8, total_delay + 0.3)
        return round(total_delay, 2)

    @classmethod
    def maybe_inject_typo(
        cls,
        text: str,
        base_probability: float = settings.typo_base_probability,
    ) -> Tuple[str, Optional[str]]:
        """
        With a calculated probability, injects a single keyboard typo into a word,
        and provides the follow-up correction string (e.g. '*الكلمة').
        """
        circadian = circadian_engine.evaluate_circadian_state()
        prob = base_probability * circadian["typo_multiplier"]

        words = text.split()
        if len(words) < 3 or random.random() > prob:
            return text, None

        # Pick candidate word with length >= 4
        candidates = [i for i, w in enumerate(words) if len(w) >= 4 and not w.startswith("http")]
        if not candidates:
            return text, None

        target_idx = random.choice(candidates)
        target_word = words[target_idx]

        # Find a character that has keyboard neighbors
        char_indices = [
            i for i, ch in enumerate(target_word) if ch in cls.ARABIC_KEYBOARD_NEIGHBORS
        ]
        if not char_indices:
            return text, None

        char_idx = random.choice(char_indices)
        orig_char = target_word[char_idx]
        typo_char = random.choice(cls.ARABIC_KEYBOARD_NEIGHBORS[orig_char])

        typo_word = target_word[:char_idx] + typo_char + target_word[char_idx + 1 :]
        words[target_idx] = typo_word

        corrupted_text = " ".join(words)
        correction_text = f"*{target_word}"

        logger.debug(f"Injected typo: '{target_word}' -> '{typo_word}' | Correction: '{correction_text}'")
        return corrupted_text, correction_text

    @classmethod
    def prepare_message_bursts(
        cls,
        text: str,
        is_shy: bool = False,
        is_group: bool = False,
        max_bubbles: int = 3,
    ) -> List[BurstMessage]:
        """
        Full pipeline: partitions text into bubbles, computes timing delays, and injects self-corrections.
        Respects group consolidation and max_bubbles limits.
        """
        bubbles = cls.split_into_multi_bubble_bursts(text, is_group=is_group, max_bubbles=max_bubbles)
        burst_items: List[BurstMessage] = []

        for i, bubble in enumerate(bubbles):
            corrupted, correction = cls.maybe_inject_typo(bubble)
            delay = cls.calculate_typing_delay(corrupted, is_shy=is_shy)

            burst_items.append(
                BurstMessage(
                    text=corrupted,
                    typing_delay_sec=delay,
                    has_typo=bool(correction),
                    correction_text=correction,
                )
            )

        return burst_items


human_typer = HumanTyperSimulator()
