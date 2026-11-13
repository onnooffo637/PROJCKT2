"""
Live Soundscape & Background Ambiance Mixer (Project Aether-Human V4.0)
Mixes environmental audio textures (cafe chatter, street noise, keyboard typing, night room)
to provide high-fidelity acoustic presence during VoIP calls.
"""

from __future__ import annotations

import logging
import random
from typing import Dict, Any

logger = logging.getLogger("Aether.VoIP.SoundscapeMixer")


class SoundscapeMixer:
    """
    Simulates acoustic background environments.
    """

    PRESETS = {
        "room_quiet": {
            "name": "غرفة هادئة",
            "ambient_gain_db": -28,
            "sound_elements": ["subtle_fan_hum", "room_reverb"],
        },
        "cafe_shami": {
            "name": "مقهى شامي دافئ",
            "ambient_gain_db": -22,
            "sound_elements": ["distant_chatter", "coffee_cups_clink"],
        },
        "street_traffic": {
            "name": "شارع دمشقي متحرك",
            "ambient_gain_db": -20,
            "sound_elements": ["distant_cars", "breeze"],
        },
        "coding_workstation": {
            "name": "مكتب البرمجة",
            "ambient_gain_db": -24,
            "sound_elements": ["mechanical_keyboard_clicks", "pc_fans"],
        },
        "night_whisper": {
            "name": "سكون الليل",
            "ambient_gain_db": -35,
            "sound_elements": ["crickets_very_faint", "pure_silence"],
        },
    }

    @classmethod
    def get_soundscape_for_hour(cls, local_hour: int) -> Dict[str, Any]:
        """
        Dynamically selects ambient soundscape matching Omar's circadian environment.
        """
        if 0 <= local_hour < 7:
            preset_key = "night_whisper"
        elif 7 <= local_hour < 12:
            preset_key = "room_quiet"
        elif 12 <= local_hour < 18:
            preset_key = random.choice(["cafe_shami", "coding_workstation"])
        else:
            preset_key = random.choice(["room_quiet", "coding_workstation", "street_traffic"])

        logger.debug(f"Selected audio soundscape: {preset_key} for hour {local_hour}")
        return cls.PRESETS[preset_key]


soundscape_mixer = SoundscapeMixer()

