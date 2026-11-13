"""
Hyper-Realistic Human Voice Engine Module.
Pure Edge-TTS Architecture re-exported from `aether_human_core.multimodal.realistic_voice`.
"""

from __future__ import annotations

from aether_human_core.multimodal.realistic_voice import (
    clean_for_human_speech,
    clean_for_edge_fallback,
    RealisticVoiceGenerator,
    RealisticVoice,
    voice_generator,
    realistic_voice_generator,
    synthesize_voice,
    EMOJI_AND_SYMBOL_REGEX,
)

__all__ = [
    "clean_for_human_speech",
    "clean_for_edge_fallback",
    "RealisticVoiceGenerator",
    "RealisticVoice",
    "voice_generator",
    "realistic_voice_generator",
    "synthesize_voice",
    "EMOJI_AND_SYMBOL_REGEX",
]
