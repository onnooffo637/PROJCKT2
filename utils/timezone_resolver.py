"""
Dynamic Country/City Timezone Resolver for Project Aether-Human.
Strictly decouples bot clock calculation from the host/device local timezone by
fetching Coordinated Universal Time (UTC) first and programmatically converting
it to the active bot's IANA timezone (e.g. Asia/Damascus for Syria, Africa/Cairo for Egypt,
Asia/Baghdad for Iraq, Asia/Riyadh for Saudi Arabia, Africa/Algiers for Algeria).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

logger = logging.getLogger("Aether.Utils.TimezoneResolver")

# ---------------------------------------------------------------------------
# Mapping: keyword fragment -> (iana_tz, country_ar, city_ar, flag, fallback_utc_offset)
# ---------------------------------------------------------------------------
_RAW_TZ_ENTRIES: List[Tuple[List[str], Tuple[str, str, str, str, float]]] = [
    # Syria
    (
        ["syria", "syrian", "damascus", "سوريا", "سوريه", "سوري", "دمشق", "دمشقي", "حلب", "حمص", "حماه", "اللاذقيه", "طرطوس", "شامي", "شاميه", "الشام"],
        ("Asia/Damascus", "سوريا", "دمشق", "🇸🇾", 3.0),
    ),
    # Iraq
    (
        ["iraq", "iraqi", "baghdad", "العراق", "عراق", "عراقي", "عراقيه", "بغداد", "بغدادي", "بغداديه", "بصره", "البصره", "موصل", "الموصل", "اربيل", "كربلاء", "النجف"],
        ("Asia/Baghdad", "العراق", "بغداد", "🇮🇶", 3.0),
    ),
    # Algeria
    (
        ["algeria", "algerian", "algiers", "الجزائر", "جزائر", "جزائري", "جزائريه", "وهران", "قسنطينه", "عنابه"],
        ("Africa/Algiers", "الجزائر", "الجزائر", "🇩🇿", 1.0),
    ),
    # Saudi Arabia / Gulf
    (
        ["saudi", "riyadh", "jeddah", "السعوديه", "سعوديه", "سعودي", "الرياض", "رياض", "جده", "مكه", "المدينه", "الدمام", "الخبر", "حجازي", "نجدي", "خليجي", "الخليج", "gulf"],
        ("Asia/Riyadh", "السعودية", "الرياض", "🇸🇦", 3.0),
    ),
    # Kuwait
    (
        ["kuwait", "kuwaiti", "الكويت", "كويت", "كويتي", "كويتيه"],
        ("Asia/Kuwait", "الكويت", "الكويت", "🇰🇼", 3.0),
    ),
    # UAE
    (
        ["uae", "emirati", "dubai", "abu dhabi", "الامارات", "امارات", "اماراتي", "اماراتيه", "دبي", "ابوظبي", "الشارقه"],
        ("Asia/Dubai", "الإمارات", "دبي", "🇦🇪", 4.0),
    ),
    # Qatar
    (
        ["qatar", "qatari", "doha", "قطر", "قطري", "قطريه", "الدوحه", "دوحه"],
        ("Asia/Qatar", "قطر", "الدوحة", "🇶🇦", 3.0),
    ),
    # Bahrain
    (
        ["bahrain", "bahraini", "manama", "البحرين", "بحرين", "بحريني", "المنامه"],
        ("Asia/Bahrain", "البحرين", "المنامة", "🇧🇭", 3.0),
    ),
    # Oman
    (
        ["oman", "omani", "muscat", "سلطنه عمان", "مسقط", "عماني", "عمانيه"],
        ("Asia/Muscat", "عُمان", "مسقط", "🇴🇲", 4.0),
    ),
    # Lebanon
    (
        ["lebanon", "lebanese", "beirut", "لبنان", "لبناني", "لبنانيه", "بيروت", "صيدا"],
        ("Asia/Beirut", "لبنان", "بيروت", "🇱🇧", 2.0),
    ),
    # Jordan
    (
        ["jordan", "jordanian", "amman", "الاردن", "اردن", "اردني", "اردنيه", "عمان", "اربد", "الزرقاء", "نشمي", "نشميه"],
        ("Asia/Amman", "الأردن", "عمّان", "🇯🇴", 3.0),
    ),
    # Palestine
    (
        ["palestine", "palestinian", "jerusalem", "gaza", "فلسطين", "فلسطيني", "فلسطينيه", "القدس", "قدس", "غزه", "رام الله", "نابلس", "الخليل", "حيفا", "يافا"],
        ("Asia/Hebron", "فلسطين", "القدس", "🇵🇸", 2.0),
    ),
    # Morocco
    (
        ["morocco", "moroccan", "casablanca", "rabat", "المغرب", "مغرب", "مغربي", "مغربيه", "الرباط", "رباط", "الدار البيضاء", "كازا", "مراكش", "طنجه", "فاس"],
        ("Africa/Casablanca", "المغرب", "الرباط", "🇲🇦", 1.0),
    ),
    # Tunisia
    (
        ["tunisia", "tunisian", "tunis", "تونس", "تونسي", "تونسيه", "صفاقس", "سوسه"],
        ("Africa/Tunis", "تونس", "تونس", "🇹🇳", 1.0),
    ),
    # Libya
    (
        ["libya", "libyan", "tripoli", "ليبيا", "ليبي", "ليبيه", "طرابلس", "بنغازي"],
        ("Africa/Tripoli", "ليبيا", "طرابلس", "🇱🇾", 2.0),
    ),
    # Sudan
    (
        ["sudan", "sudanese", "khartoum", "السودان", "سودان", "سوداني", "سودانيه", "الخرطوم", "خرطوم"],
        ("Africa/Khartoum", "السودان", "الخرطوم", "🇸🇩", 2.0),
    ),
    # Yemen
    (
        ["yemen", "yemeni", "sanaa", "aden", "اليمن", "يمن", "يمني", "يمنيه", "صنعاء", "عدن", "تعز"],
        ("Asia/Aden", "اليمن", "صنعاء", "🇾🇪", 3.0),
    ),
    # Turkey
    (
        ["turkey", "turkish", "istanbul", "ankara", "تركيا", "تركي", "تركيه", "اسطنبول", "انقره"],
        ("Europe/Istanbul", "تركيا", "إسطنبول", "🇹🇷", 3.0),
    ),
    # Egypt
    (
        ["egypt", "egyptian", "cairo", "alexandria", "مصر", "مصري", "مصريه", "القاهره", "قاهره", "قاهري", "قاهريه", "الاسكندريه", "اسكندريه", "المنصوره", "منصوره", "شبرا", "الدقي", "الجيزه", "طنطا", "الصعيد", "الساحل"],
        ("Africa/Cairo", "مصر", "القاهرة", "🇪🇬", 2.0),
    ),
    # Europe / World Common
    (
        ["london", "uk", "britain", "لندن", "بريطانيا"],
        ("Europe/London", "بريطانيا", "لندن", "🇬🇧", 0.0),
    ),
    (
        ["paris", "france", "باريس", "فرنسا"],
        ("Europe/Paris", "فرنسا", "باريس", "🇫🇷", 1.0),
    ),
    (
        ["berlin", "germany", "برلين", "المانيا"],
        ("Europe/Berlin", "ألمانيا", "برلين", "🇩🇪", 1.0),
    ),
    (
        ["new york", "usa", "america", "نيويورك", "امريكا", "واشنطن"],
        ("America/New_York", "أمريكا", "نيويورك", "🇺🇸", -5.0),
    ),
]


def _normalise(text: str) -> str:
    """Normalise Arabic/English text for deterministic key lookup."""
    if not text:
        return ""
    return (
        text.lower()
        .strip()
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ة", "ه")
        .replace("ى", "ي")
        .replace("ّ", "")
        .replace("َ", "")
        .replace("ُ", "")
        .replace("ِ", "")
        .replace("ْ", "")
    )


_TZ_FULL_MAP: Dict[str, Tuple[str, str, str, str, float]] = {}
for _keywords, _meta in _RAW_TZ_ENTRIES:
    for _kw in _keywords:
        _TZ_FULL_MAP[_normalise(_kw)] = _meta


def resolve_timezone_meta(location: str) -> Optional[Tuple[str, str, str, str, float]]:
    """
    Matches a free-form location/dialect string to (iana_tz, country_ar, city_ar, flag, utc_offset).
    Returns None if no match is found.
    """
    if not location or not location.strip():
        return None

    norm = _normalise(location)
    if not norm:
        return None

    # 1. Exact match
    if norm in _TZ_FULL_MAP:
        return _TZ_FULL_MAP[norm]

    # 2. Token/word match (prioritizes whole words in order of appearance)
    import re
    words = [w for w in re.split(r"[\s,،.\-_/()\[\]\"']+", norm) if len(w) >= 2]
    for w in words:
        if w in _TZ_FULL_MAP:
            return _TZ_FULL_MAP[w]
        # Strip common Arabic prefixes 'ال', 'ب', 'ل', 'و'
        if w.startswith("ال") and len(w) > 3 and w[2:] in _TZ_FULL_MAP:
            return _TZ_FULL_MAP[w[2:]]
        if w[0] in ("ب", "ل", "و") and len(w) > 3 and w[1:] in _TZ_FULL_MAP:
            return _TZ_FULL_MAP[w[1:]]

    # 3. Substring match (longest keyword wins)
    best_key: Optional[str] = None
    for key in _TZ_FULL_MAP:
        if len(key) >= 3 and key in norm:
            if best_key is None or len(key) > len(best_key):
                best_key = key
    if best_key:
        return _TZ_FULL_MAP[best_key]

    return None


def resolve_timezone(location: str) -> Tuple[str, str, str]:
    """
    Backward-compatible resolver returning (iana_tz, country_ar, city_ar).
    """
    meta = resolve_timezone_meta(location)
    if meta:
        return (meta[0], meta[1], meta[2])
    return ("UTC", "غير محدد", "غير محدد")


def compute_utc_to_bot_time(iana_tz: str, fallback_offset_hours: float = 3.0) -> Dict[str, Any]:
    """
    Strictly fetches Coordinated Universal Time (UTC) first, completely decoupled from
    the local phone/server timezone (e.g., Algeria), and converts it programmatically
    to the target bot's IANA timezone (`iana_tz`).
    """
    utc_now = datetime.now(timezone.utc)
    try:
        tz_obj = ZoneInfo(iana_tz)
        bot_now = utc_now.astimezone(tz_obj)
        utcoff = bot_now.utcoffset()
        actual_offset_hours = (utcoff.total_seconds() / 3600.0) if utcoff is not None else fallback_offset_hours
    except Exception:
        tz_obj_fixed = timezone(timedelta(hours=fallback_offset_hours))
        bot_now = utc_now.astimezone(tz_obj_fixed)
        actual_offset_hours = fallback_offset_hours

    hour = bot_now.hour
    minute = bot_now.minute

    if hour == 0:
        period_12h = "صباحاً"
        period_conversational = "بعد منتصف الليل"
        display_hour = 12
    elif hour < 12:
        period_12h = "صباحاً"
        period_conversational = "صباحاً"
        display_hour = hour
    elif hour == 12:
        period_12h = "مساءً"
        period_conversational = "ظهراً"
        display_hour = 12
    else:
        period_12h = "مساءً"
        period_conversational = "مساءً"
        display_hour = hour - 12

    formatted_12h_ar = f"{display_hour:02d}:{minute:02d} {period_12h}"
    formatted_short_ar = f"{display_hour}:{minute:02d} {period_conversational}"

    return {
        "utc_iso": utc_now.isoformat(),
        "bot_iso": bot_now.isoformat(),
        "iana_timezone": iana_tz,
        "utc_offset_hours": round(actual_offset_hours, 2),
        "hour": hour,
        "minute": minute,
        "second": bot_now.second,
        "display_hour_12": display_hour,
        "period_ar": period_12h,
        "formatted_time_ar": formatted_12h_ar,
        "formatted_conversational_ar": formatted_short_ar,
        "raw_time_24h": bot_now.strftime("%H:%M"),
        "weekday": bot_now.weekday(),
        "day": bot_now.day,
        "month": bot_now.month,
        "year": bot_now.year,
    }


class TimezoneResolver:
    """
    Unified high-level resolver for bot identity, timezone, flag, country/city capsule label,
    and UTC-derived local clock.
    """

    @classmethod
    def resolve_bot_timezone(
        cls,
        origin_location: str = "",
        primary_dialect: str = "",
        system_prompt: str = "",
        bio: str = "",
    ) -> Dict[str, Any]:
        """
        Resolves the active bot's timezone, flag, country, city, and live UTC-converted clock.
        Priority:
          1. `origin_location` (explicit country/city entered in Bot Factory settings, e.g. "سوريا", "بغداد")
          2. `primary_dialect` (e.g. "syrian", "iraqi", "لهجة سورية", "يتحدث باللغة العربية الفصحى، كما يجيد اللهجة السورية...")
          3. `bio` and `system_prompt` (e.g. "شاب سوري خلوق", "بنت عراقية")
          4. Default fallback: Cairo, Egypt ("Africa/Cairo", "مصر", "القاهرة", "🇪🇬", 2.0)
        """
        matched_meta: Optional[Tuple[str, str, str, str, float]] = None

        for candidate in (origin_location, primary_dialect, bio, system_prompt):
            if candidate and candidate.strip():
                matched_meta = resolve_timezone_meta(candidate)
                if matched_meta is not None:
                    break

        if matched_meta is None:
            matched_meta = ("Africa/Cairo", "مصر", "القاهرة", "🇪🇬", 2.0)

        iana_tz, country_ar, city_ar, flag, fallback_offset = matched_meta
        clock_data = compute_utc_to_bot_time(iana_tz, fallback_offset)

        # Determine the clean capsule label to show inside parentheses: e.g. "(سوريا)" or "(دمشق)" or "(بغداد)"
        clean_origin = (origin_location or "").strip()
        if (
            clean_origin
            and len(clean_origin) <= 18
            and not any(ch in clean_origin for ch in ("-", "/", "\\", "(", ")", "،", ","))
        ):
            capsule_location_ar = clean_origin
        else:
            capsule_location_ar = city_ar

        return {
            "iana_timezone": iana_tz,
            "utc_offset_hours": clock_data["utc_offset_hours"],
            "country_ar": country_ar,
            "city_ar": city_ar,
            "city_country_ar": f"{city_ar}، {country_ar}" if city_ar != country_ar else country_ar,
            "capsule_location_ar": capsule_location_ar,
            "flag": flag,
            "formatted_time_ar": clock_data["formatted_time_ar"],
            "raw_time_24h": clock_data["raw_time_24h"],
            "hour": clock_data["hour"],
            "minute": clock_data["minute"],
            "utc_iso": clock_data["utc_iso"],
        }


def get_bot_local_time(location: str) -> str:
    """
    Returns a human-readable Arabic local time string for the given location,
    strictly computed from UTC -> target IANA timezone.
    Example: "الساعة 11:35 مساءً (بتوقيت دمشق - سوريا)"
    """
    meta = resolve_timezone_meta(location)
    if not meta:
        return ""
    iana_tz, country_ar, city_ar, _flag, fallback_offset = meta
    clock = compute_utc_to_bot_time(iana_tz, fallback_offset)
    loc_label = f"{city_ar} - {country_ar}" if city_ar != country_ar else country_ar
    return f"الساعة {clock['formatted_conversational_ar']} (بتوقيت {loc_label})"


def get_bot_local_time_full(location: str) -> str:
    """
    Returns a fuller local time string including day name and date, computed strictly from UTC.
    """
    meta = resolve_timezone_meta(location)
    if not meta:
        return ""
    iana_tz, country_ar, city_ar, _flag, fallback_offset = meta
    clock = compute_utc_to_bot_time(iana_tz, fallback_offset)
    day_names = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    day_name = day_names[clock["weekday"]]
    return (
        f"{day_name}، {clock['day']}/{clock['month']}/{clock['year']} - "
        f"الساعة {clock['formatted_conversational_ar']} بتوقيت {city_ar} ({country_ar})"
    )
