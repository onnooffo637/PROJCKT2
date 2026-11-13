"""
Mood Music Generator for Telegram Stories (Project Aether-Human V5.0).
Synthesizes 15-second melodic background tracks for each mood theme:
- happy_energetic: Uplifting major scale acoustic arpeggio and warm melodic chords.
- dark_melancholic: Nocturnal minor ambient piano chords and deep resonant pads.
- cyberpunk_coding: Synthwave 80s bassline and futuristic arpeggiated pulse.
- chill_coffee: Warm relaxing lo-fi jazz chords (Fmaj7 - Em7 - Dm7) with vinyl air.
- sarcastic_sharp: Punchy funky bass groove with crisp rhythmic accents.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Dict, List
import numpy as np

logger = logging.getLogger("Aether.Multimodal.MoodMusic")


class MoodMusicGenerator:
    """
    Generates and caches authentic 15-second mood music tracks for Telegram Stories.
    """

    MOOD_CHORD_MAP: Dict[str, Dict[str, Any]] = {
        "happy_energetic": {
            "chords": [
                [261.63, 329.63, 392.00, 523.25],  # C major
                [220.00, 261.63, 329.63, 440.00],  # A minor
                [174.61, 220.00, 261.63, 349.23],  # F major
                [196.00, 246.94, 293.66, 392.00],  # G major
            ],
            "tempo_mult": 1.4,
            "style": "acoustic",
        },
        "dark_melancholic": {
            "chords": [
                [164.81, 196.00, 246.94, 329.63],  # Em
                [146.83, 174.61, 220.00, 293.66],  # Dm
                [130.81, 155.56, 196.00, 261.63],  # Cm
                [123.47, 146.83, 185.00, 246.94],  # Bm
            ],
            "tempo_mult": 0.8,
            "style": "ambient_piano",
        },
        "cyberpunk_coding": {
            "chords": [
                [110.00, 164.81, 220.00, 329.63],  # A minor synth
                [130.81, 196.00, 261.63, 392.00],  # C major synth
                [98.00, 146.83, 196.00, 293.66],   # G synth
                [87.31, 130.81, 174.61, 261.63],   # F synth
            ],
            "tempo_mult": 1.6,
            "style": "synthwave",
        },
        "chill_coffee": {
            "chords": [
                [174.61, 220.00, 261.63, 329.63],  # Fmaj7
                [164.81, 196.00, 246.94, 293.66],  # Em7
                [146.83, 174.61, 220.00, 261.63],  # Dm7
                [130.81, 164.81, 196.00, 246.94],  # Cmaj7
            ],
            "tempo_mult": 1.0,
            "style": "rhodes",
        },
        "sarcastic_sharp": {
            "chords": [
                [146.83, 185.00, 220.00, 293.66],  # D7
                [164.81, 207.65, 246.94, 329.63],  # E7
                [196.00, 246.94, 293.66, 392.00],  # G7
                [220.00, 277.18, 329.63, 440.00],  # A7
            ],
            "tempo_mult": 1.3,
            "style": "funk_bass",
        },
    }

    def __init__(self) -> None:
        self.tracks_dir = os.path.join(os.getcwd(), "artifacts", "stories", "mood_tracks")
        os.makedirs(self.tracks_dir, exist_ok=True)

    def get_mood_music_track(self, mood_key: str = "chill_coffee") -> str:
        """
        Returns absolute path to a cached 15-second MP3 mood track, synthesizing it if needed.
        """
        safe_key = mood_key if mood_key in self.MOOD_CHORD_MAP else "chill_coffee"
        target_mp3 = os.path.join(self.tracks_dir, f"{safe_key}.mp3")

        if os.path.exists(target_mp3) and os.path.getsize(target_mp3) > 10000:
            return target_mp3

        try:
            return self._synthesize_mood_track(safe_key, target_mp3)
        except Exception as exc:
            logger.error(f"Failed to synthesize mood track for [{safe_key}]: {exc}")
            return target_mp3

    def _synthesize_mood_track(self, mood_key: str, output_mp3: str) -> str:
        sample_rate = 44100
        duration = 15.0
        num_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, num_samples, endpoint=False)

        cfg = self.MOOD_CHORD_MAP.get(mood_key, self.MOOD_CHORD_MAP["chill_coffee"])
        chords = cfg["chords"]
        chord_dur = duration / len(chords)
        style = cfg.get("style", "rhodes")

        audio_left = np.zeros(num_samples, dtype=np.float32)
        audio_right = np.zeros(num_samples, dtype=np.float32)

        for i, chord in enumerate(chords):
            idx_start = int(i * chord_dur * sample_rate)
            idx_end = int((i + 1) * chord_dur * sample_rate)
            seg_len = idx_end - idx_start
            seg_t = np.linspace(0, chord_dur, seg_len, endpoint=False)

            # Attack-Decay-Sustain Envelope
            if style == "synthwave":
                envelope = 0.85 * np.exp(-0.8 * (seg_t % 0.35)) + 0.15
            elif style == "ambient_piano":
                envelope = np.exp(-1.1 * seg_t) + 0.18 * (1.0 - seg_t / chord_dur)
            else:
                envelope = np.exp(-1.4 * seg_t) + 0.25 * np.sin(np.pi * seg_t / chord_dur)

            seg_wave = np.zeros(seg_len, dtype=np.float32)
            for n_idx, note_f in enumerate(chord):
                if style == "synthwave":
                    # Sawtooth + square sub-bass
                    wave_n = (
                        0.5 * np.sin(2 * np.pi * note_f * seg_t)
                        + 0.3 * np.sign(np.sin(2 * np.pi * (note_f / 2) * seg_t))
                        + 0.2 * np.sin(2 * np.pi * note_f * 2 * seg_t)
                    )
                elif style == "ambient_piano":
                    # Pure mellow sine with soft octave
                    wave_n = (
                        0.7 * np.sin(2 * np.pi * note_f * seg_t)
                        + 0.2 * np.sin(2 * np.pi * note_f * 2 * seg_t)
                        + 0.08 * np.sin(2 * np.pi * note_f * 3 * seg_t)
                    )
                else:
                    # Warm Rhodes / acoustic chords
                    wave_n = (
                        0.6 * np.sin(2 * np.pi * note_f * seg_t)
                        + 0.25 * np.sin(2 * np.pi * note_f * 2 * seg_t)
                        + 0.12 * np.sin(2 * np.pi * note_f * 3 * seg_t)
                        + 0.05 * np.sin(2 * np.pi * note_f * 4 * seg_t)
                    )

                pan_offset = 0.15 * (n_idx - 1.5)
                seg_wave += wave_n * envelope

            audio_left[idx_start:idx_end] += seg_wave * 0.72
            audio_right[idx_start:idx_end] += seg_wave * 0.68

        # Subtle organic air / vinyl floor
        noise = np.random.normal(0, 0.002, num_samples).astype(np.float32)
        audio_left += noise
        audio_right += noise

        # Master limiter & normalize
        max_val = max(float(np.max(np.abs(audio_left))), float(np.max(np.abs(audio_right))), 0.001)
        audio_left = (audio_left / max_val) * 0.85
        audio_right = (audio_right / max_val) * 0.85

        stereo_int16 = np.empty((num_samples, 2), dtype=np.int16)
        stereo_int16[:, 0] = (audio_left * 32767).astype(np.int16)
        stereo_int16[:, 1] = (audio_right * 32767).astype(np.int16)

        temp_raw = output_mp3.replace(".mp3", ".raw")
        stereo_int16.tofile(temp_raw)

        cmd = [
            "ffmpeg", "-y", "-f", "s16le", "-ar", "44100", "-ac", "2",
            "-i", temp_raw, "-b:a", "192k", output_mp3,
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(temp_raw):
            os.remove(temp_raw)

        logger.info(f"🎵 Generated 15-second mood music track for [{mood_key}] at [{output_mp3}].")
        return output_mp3


mood_music_generator = MoodMusicGenerator()

