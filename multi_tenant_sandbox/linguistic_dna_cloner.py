"""
Linguistic DNA Cloner (Project Aether-Human V3.0)
Extracts conversational traits, cadence, slang, emojis, and styling from user sample text
to clone their linguistic DNA into their private sandbox persona.
"""

from __future__ import annotations

import collections
import logging
import re
from typing import Any, Dict, List
from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer

logger = logging.getLogger("Aether.MultiTenant.DNACloner")

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)

STOPWORDS = {
    "من", "إلى", "عن", "على", "في", "هو", "هي", "أن", "إن", "كان", "كانت",
    "هذا", "هذه", "ذلك", "تلك", "التي", "الذي", "مع", "أو", "ثم", "بل", "لكن",
    "و", "ف", "ب", "ل", "ك", "ما", "لا", "لم", "لن", "إلا", "غير", "حتى"
}


class LinguisticDNACloner:
    """
    Analyzes sample text to clone user vocabulary, cadence, and habits.
    """

    @classmethod
    def analyze_sample_text(cls, text: str) -> Dict[str, Any]:
        """
        Extracts DNA metrics from a block of text or chat export.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        total_lines = max(1, len(lines))

        # 1. Emojis extraction
        emojis_found = EMOJI_PATTERN.findall(text)
        emoji_counts = collections.Counter(emojis_found)
        top_emojis = [e for e, _ in emoji_counts.most_common(5)]

        # 2. Words & Slang extraction
        words = re.findall(r"[\w']+", text.lower())
        total_words = max(1, len(words))
        clean_words = [w for w in words if w not in STOPWORDS and len(w) > 2]
        word_counts = collections.Counter(clean_words)
        top_words = [w for w, count in word_counts.most_common(12) if count >= 1]

        # 3. Sentence Length & Cadence
        avg_line_words = total_words / total_lines
        is_short_burst = avg_line_words <= 6.5

        # 4. Punctuation habits
        uses_ellipsis = "..." in text or "…" in text
        uses_multiple_exclamations = "!!" in text or "!؟" in text or "؟!" in text
        laughter_patterns = ["هههه", "ههه", "xd", "lol", "كككك"]
        has_laughter = any(pat in text.lower() for pat in laughter_patterns)

        dna_profile = {
            "top_emojis": top_emojis,
            "favorite_words": top_words,
            "avg_words_per_message": round(avg_line_words, 1),
            "is_short_burst_style": is_short_burst,
            "uses_ellipsis": uses_ellipsis,
            "uses_intense_punctuation": uses_multiple_exclamations,
            "has_signature_laughter": has_laughter,
        }

        return dna_profile

    @classmethod
    def clone_and_apply_to_user(cls, user_id: int, sample_text: str) -> Dict[str, Any]:
        """
        Extracts DNA and binds it directly to the user's isolated persona.
        """
        dna = cls.analyze_sample_text(sample_text)
        persona_virtualizer.attach_linguistic_dna(user_id, dna)
        logger.info(f"🧬 Linguistic DNA successfully cloned for User [{user_id}]: {dna}")
        return dna


linguistic_cloner = LinguisticDNACloner()

