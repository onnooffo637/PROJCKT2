"""
Story Song Manager for Telegram Stories (Project Aether-Human V5.0).
Provides authentic Arabic/Egyptian songs with real vocals and singing for Telegram Stories:
- Categorized by mood (chill_coffee, happy_energetic, dark_melancholic, cyberpunk_coding, sarcastic_sharp).
- Supports user-provided custom songs in `artifacts/stories/songs/`.
- Extracts high-quality 20-second vocal choruses with smooth fade-in and fade-out.
- Provides music sticker metadata (Artist - Song Title) for story rendering.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Aether.Multimodal.StorySong")


class StorySongManager:
    """
    Manages authentic vocal songs for Telegram Stories matching Omar's persona and mood.
    """

    CURATED_SONGS: Dict[str, List[Dict[str, Any]]] = {
        "chill_coffee": [
            {
                "title": "فاضي شوية",
                "artist": "حمزة نمرة",
                "query": "حمزة نمرة فاضي شوية official audio",
                "start": 45,
                "duration": 20,
            },
            {
                "title": "تملي معاك",
                "artist": "عمرو دياب",
                "query": "عمرو دياب تملي معاك audio",
                "start": 35,
                "duration": 20,
            },
            {
                "title": "يمكن خير",
                "artist": "رامي صبري",
                "query": "رامي صبري يمكن خير audio",
                "start": 45,
                "duration": 20,
            },
        ],
        "happy_energetic": [
            {
                "title": "إيه اليوم الحلو ده",
                "artist": "أحمد سعد",
                "query": "احمد سعد ايه اليوم الحلو ده official audio",
                "start": 30,
                "duration": 20,
            },
            {
                "title": "يا أنا يا لأ",
                "artist": "عمرو دياب",
                "query": "عمرو دياب يا انا يا لاء audio",
                "start": 30,
                "duration": 20,
            },
            {
                "title": "وسع وسع",
                "artist": "أحمد سعد",
                "query": "احمد سعد وسع وسع audio",
                "start": 35,
                "duration": 20,
            },
        ],
        "dark_melancholic": [
            {
                "title": "البخت",
                "artist": "ويجز",
                "query": "ويجز البخت audio",
                "start": 32,
                "duration": 20,
            },
            {
                "title": "تلك قضية",
                "artist": "كايروكي",
                "query": "كايروكي تلك قضية audio",
                "start": 40,
                "duration": 20,
            },
            {
                "title": "دلوقتي عجبناكوا",
                "artist": "بهاء سلطان",
                "query": "بهاء سلطان دلوقتي عجبناكوا audio",
                "start": 40,
                "duration": 20,
            },
        ],
        "cyberpunk_coding": [
            {
                "title": "غابة",
                "artist": "مروان بابلو",
                "query": "مروان بابلو غابة audio",
                "start": 25,
                "duration": 20,
            },
            {
                "title": "كيفي كدا",
                "artist": "ويجز",
                "query": "ويجز كيفي كدا audio",
                "start": 32,
                "duration": 20,
            },
            {
                "title": "روما",
                "artist": "كايروكي",
                "query": "كايروكي روما audio",
                "start": 35,
                "duration": 20,
            },
        ],
        "sarcastic_sharp": [
            {
                "title": "سندباد",
                "artist": "مروان بابلو",
                "query": "مروان بابلو سندباد audio",
                "start": 30,
                "duration": 20,
            },
            {
                "title": "آه لو لعبت يا زهر",
                "artist": "أحمد شيبة",
                "query": "احمد شيبة اه لو لعبت يا زهر audio",
                "start": 35,
                "duration": 20,
            },
            {
                "title": "أنا غلطان",
                "artist": "بهاء سلطان",
                "query": "بهاء سلطان انا غلطان audio",
                "start": 35,
                "duration": 20,
            },
        ],
    }

    def __init__(self) -> None:
        self.base_songs_dir = os.path.join(os.getcwd(), "artifacts", "stories", "songs")
        self.cached_dir = os.path.join(self.base_songs_dir, "cached")
        os.makedirs(self.cached_dir, exist_ok=True)
        for mood in self.CURATED_SONGS.keys():
            os.makedirs(os.path.join(self.base_songs_dir, mood), exist_ok=True)

    def _find_user_custom_song(self, mood_key: str) -> Optional[Dict[str, Any]]:
        """
        Checks if the user has dropped any custom audio files in:
        1. artifacts/stories/songs/{mood_key}/
        2. artifacts/stories/songs/ (root)
        """
        candidate_dirs = [
            os.path.join(self.base_songs_dir, mood_key),
            self.base_songs_dir,
        ]
        supported_exts = (".mp3", ".wav", ".m4a", ".ogg")

        for c_dir in candidate_dirs:
            if not os.path.exists(c_dir):
                continue
            for fname in os.listdir(c_dir):
                fpath = os.path.join(c_dir, fname)
                if os.path.isfile(fpath) and fname.lower().endswith(supported_exts):
                    if "cached" in fpath.lower() or fname.startswith("temp_"):
                        continue
                    # Parse song title & artist from filename (e.g. "Amr Diab - Tamally Maak.mp3")
                    base_name = os.path.splitext(fname)[0]
                    if " - " in base_name:
                        artist, title = base_name.split(" - ", 1)
                    else:
                        artist, title = "أغنية", base_name

                    # Prepare cut snippet if song is long
                    processed_clip = self._prepare_custom_clip(fpath, mood_key)
                    return {
                        "audio_path": processed_clip,
                        "song_title": title.strip(),
                        "artist": artist.strip(),
                        "display_sticker": f"🎵 {artist.strip()} - {title.strip()}",
                    }
        return None

    def _prepare_custom_clip(self, input_path: str, mood_key: str) -> str:
        """Slices a 20-second clip with fade-in and fade-out if input is longer than 25s."""
        out_path = os.path.join(self.cached_dir, f"custom_{mood_key}_{os.path.basename(input_path)}.mp3")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 20000:
            return out_path

        cmd = [
            "ffmpeg", "-y", "-ss", "00:00:15", "-t", "20",
            "-i", input_path,
            "-af", "afade=t=in:ss=0:d=1.5,afade=t=out:st=18:d=2",
            "-c:a", "libmp3lame", "-b:a", "192k", out_path,
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
                return out_path
        except Exception as exc:
            logger.debug(f"Custom clip slice notice ({exc}), using original path.")
        return input_path

    async def get_story_song(self, mood_key: str = "chill_coffee") -> Dict[str, Any]:
        """
        Retrieves an authentic vocal song for the story:
        1. User's custom songs in `artifacts/stories/songs/{mood}` or root
        2. Cached authentic Egyptian song clips in `artifacts/stories/songs/cached/`
        3. Dynamic download & slice via yt-dlp
        4. Fallback to mood instrumental music generator
        """
        safe_mood = mood_key if mood_key in self.CURATED_SONGS else "chill_coffee"

        # 1. User custom song
        custom_song = self._find_user_custom_song(safe_mood)
        if custom_song and os.path.exists(custom_song["audio_path"]):
            logger.info(f"🎶 Using custom user song: {custom_song['display_sticker']}")
            return custom_song

        # 2. Cached mood clip
        cached_clip = os.path.join(self.cached_dir, f"{safe_mood}_clip.mp3")
        curated_list = self.CURATED_SONGS.get(safe_mood, self.CURATED_SONGS["chill_coffee"])
        curated_info = curated_list[0]

        if os.path.exists(cached_clip) and os.path.getsize(cached_clip) > 30000:
            return {
                "audio_path": cached_clip,
                "song_title": curated_info["title"],
                "artist": curated_info["artist"],
                "display_sticker": f"🎵 {curated_info['artist']} - {curated_info['title']}",
            }

        # 3. Dynamic download in background thread
        try:
            downloaded_data = await asyncio.to_thread(self._download_and_extract_song, curated_info, safe_mood)
            if downloaded_data and os.path.exists(downloaded_data["audio_path"]):
                return downloaded_data
        except Exception as exc:
            logger.warning(f"Dynamic song fetch notice for [{safe_mood}]: {exc}")

        # 4. Fallback to mood music generator
        try:
            from aether_human_core.multimodal_engine.acoustic_voice.mood_music_generator import mood_music_generator
            fallback_track = mood_music_generator.get_mood_music_track(safe_mood)
            return {
                "audio_path": fallback_track,
                "song_title": "موسيقى",
                "artist": "عمر",
                "display_sticker": "🎵 روقان وموسيقى",
            }
        except Exception as exc:
            logger.error(f"Fallback track notice: {exc}")
            return {
                "audio_path": cached_clip,
                "song_title": curated_info["title"],
                "artist": curated_info["artist"],
                "display_sticker": f"🎵 {curated_info['artist']} - {curated_info['title']}",
            }

    def _download_and_extract_song(self, song_meta: Dict[str, Any], mood_key: str) -> Optional[Dict[str, Any]]:
        """Downloads audio via yt-dlp and extracts a 20s chorus clip."""
        import yt_dlp

        target_clip = os.path.join(self.cached_dir, f"{mood_key}_clip.mp3")
        temp_full = os.path.join(self.cached_dir, f"temp_{mood_key}.%(ext)s")
        temp_mp3 = os.path.join(self.cached_dir, f"temp_{mood_key}.mp3")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": temp_full,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True,
            "default_search": "ytsearch1",
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(f"ytsearch1:{song_meta['query']}", download=True)

            if os.path.exists(temp_mp3):
                start = song_meta.get("start", 30)
                dur = song_meta.get("duration", 20)
                cmd = [
                    "ffmpeg", "-y", "-ss", str(start), "-t", str(dur),
                    "-i", temp_mp3,
                    "-af", f"afade=t=in:ss=0:d=1.5,afade=t=out:st={dur-2}:d=2",
                    "-c:a", "libmp3lame", "-b:a", "192k", target_clip,
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                try:
                    os.remove(temp_mp3)
                except Exception:
                    pass

                if os.path.exists(target_clip) and os.path.getsize(target_clip) > 20000:
                    return {
                        "audio_path": target_clip,
                        "song_title": song_meta["title"],
                        "artist": song_meta["artist"],
                        "display_sticker": f"🎵 {song_meta['artist']} - {song_meta['title']}",
                    }
        except Exception as exc:
            logger.warning(f"Error downloading song {song_meta['title']}: {exc}")
        return None


story_song_manager = StorySongManager()

