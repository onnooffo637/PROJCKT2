"""
Zero-Disk-Bloat File & Stream Compressor for Project Aether-Human (V2.0).
Provides in-memory stream validation, image optimization to WebP,
safe temporary file lifecycles, and memory-mapped text extraction.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import logging
from typing import Optional, Tuple, Dict, Any, Generator, BinaryIO
from contextlib import contextmanager

from PIL import Image

logger = logging.getLogger("Aether.CloudGuard.Compressor")


class FileStreamCompressor:
    """
    Zero-Disk-Bloat file processing pipeline for media, images, audio, and documents.
    """

    # Maximum allowed payload sizes (in bytes)
    MAX_IMAGE_BYTES = 20 * 1024 * 1024      # 20 MB
    MAX_AUDIO_BYTES = 50 * 1024 * 1024      # 50 MB
    MAX_DOCUMENT_BYTES = 30 * 1024 * 1024   # 30 MB

    TARGET_IMAGE_MAX_DIMENSION = 1920
    TARGET_WEBP_QUALITY = 82

    @classmethod
    def compress_image_to_webp(
        cls,
        input_data: bytes | BinaryIO,
        max_dimension: int = TARGET_IMAGE_MAX_DIMENSION,
        quality: int = TARGET_WEBP_QUALITY,
    ) -> bytes:
        """
        Compresses and resizes an image entirely in RAM into optimized WebP.
        Ensures zero temporary files on disk.
        """
        try:
            if isinstance(input_data, bytes):
                stream = io.BytesIO(input_data)
            else:
                stream = input_data

            with Image.open(stream) as img:
                # Convert color modes
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    converted = img.convert("RGBA")
                else:
                    converted = img.convert("RGB")

                # Downscale proportionally if larger than maximum dimension
                width, height = converted.size
                if max(width, height) > max_dimension:
                    scale = max_dimension / max(width, height)
                    new_size = (int(width * scale), int(height * scale))
                    converted = converted.resize(new_size, Image.Resampling.LANCZOS)

                output_stream = io.BytesIO()
                converted.save(
                    output_stream,
                    format="WEBP",
                    quality=quality,
                    method=4,
                    optimize=True,
                )
                compressed_bytes = output_stream.getvalue()
                logger.debug(
                    f"Optimized image: {len(input_data) if isinstance(input_data, bytes) else '?'} bytes -> "
                    f"{len(compressed_bytes)} bytes WebP"
                )
                return compressed_bytes
        except Exception as exc:
            logger.error(f"Image compression failed: {exc}")
            if isinstance(input_data, bytes):
                return input_data
            input_data.seek(0)
            return input_data.read()

    @classmethod
    def extract_text_from_document(
        cls,
        filename: str,
        data: bytes,
        max_chars: int = 50000,
    ) -> str:
        """
        Extracts plain text from documents (TXT, MD, CSV, JSON, PDF) in memory.
        """
        lower_name = filename.lower()

        # 1. Plain text formats
        if any(lower_name.endswith(ext) for ext in [".txt", ".md", ".csv", ".json", ".py", ".html", ".log"]):
            for encoding in ("utf-8", "utf-8-sig", "windows-1256", "latin-1"):
                try:
                    text = data.decode(encoding)
                    return text[:max_chars]
                except UnicodeDecodeError:
                    continue
            return data.decode("utf-8", errors="replace")[:max_chars]

        # 2. PDF extraction (in-memory parsing without requiring external bulky C binaries)
        if lower_name.endswith(".pdf"):
            return cls._extract_text_from_pdf_stream(data, max_chars=max_chars)

        return f"[الملف المرفق: {filename} ({len(data)} بايت) - نوع غير مدعوم للاستخراج النصي المباشر]"

    @classmethod
    def _extract_text_from_pdf_stream(cls, data: bytes, max_chars: int = 50000) -> str:
        """
        Extracts stream text blocks from PDF binary data safely in memory.
        """
        extracted_chunks: list[str] = []
        try:
            # Pattern matching text blocks inside PDF streams: BT ... ET
            stream_pattern = re.compile(rb"stream[\r\n]+(.*?)[\r\n]+endstream", re.DOTALL)
            text_pattern = re.compile(rb"\((.*?)\)[\s]*T[jJ]", re.DOTALL)

            matches = stream_pattern.findall(data)
            for raw_stream in matches:
                # Some streams might be FlateDecode compressed; try zlib if possible
                import zlib
                decompressed = None
                try:
                    decompressed = zlib.decompress(raw_stream)
                except Exception:
                    decompressed = raw_stream

                if decompressed:
                    texts = text_pattern.findall(decompressed)
                    for t in texts:
                        try:
                            # Try UTF-8 or Latin-1
                            decoded = t.decode("utf-8", errors="ignore").strip()
                            if decoded and len(decoded) > 1:
                                extracted_chunks.append(decoded)
                        except Exception:
                            pass

            full_text = " ".join(extracted_chunks)
            if len(full_text.strip()) > 20:
                return full_text[:max_chars]
            else:
                # Fallback: scan for any printable strings in data
                ascii_words = re.findall(rb"[a-zA-Z0-9\u0600-\u06FF]{3,}", data)
                sample = " ".join(w.decode("utf-8", errors="ignore") for w in ascii_words[:300])
                return sample if sample else "[ملف PDF ممسوح ضوئياً أو مشفر]"
        except Exception as exc:
            logger.warning(f"PDF extraction notice: {exc}")
            return "[تعذر قراءة محتوى PDF نصياً]"

    @classmethod
    @contextmanager
    def safe_temporary_file(
        cls,
        suffix: str = "",
        prefix: str = "aether_temp_",
    ) -> Generator[str, None, None]:
        """
        Context manager ensuring absolute zero disk bloat:
        guarantees that any temporary file created on disk is strictly unlinked and removed.
        """
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)
            yield temp_path
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.debug(f"Safely purged temporary disk artifact: {temp_path}")
                except Exception as exc:
                    logger.warning(f"Could not remove temporary file {temp_path}: {exc}")


file_compressor = FileStreamCompressor()

