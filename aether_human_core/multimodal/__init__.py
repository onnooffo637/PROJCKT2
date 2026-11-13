"""
Multimodal Bridge Package for Project Aether-Human.
Re-exports Hyper-Realistic Human Voice Engine and Raw Smartphone Selfie Generator.
"""

from aether_human_core.multimodal.realistic_voice import (
    RealisticVoice,
    RealisticVoiceGenerator,
    clean_for_human_speech,
    voice_generator,
)
from aether_human_core.multimodal.image_generator import (
    FaceLockIdentityPipeline,
    PhotoVariationEngine,
    face_lock_pipeline,
    photo_variation_engine,
)

__all__ = [
    "RealisticVoice",
    "RealisticVoiceGenerator",
    "clean_for_human_speech",
    "voice_generator",
    "FaceLockIdentityPipeline",
    "PhotoVariationEngine",
    "face_lock_pipeline",
    "photo_variation_engine",
]

