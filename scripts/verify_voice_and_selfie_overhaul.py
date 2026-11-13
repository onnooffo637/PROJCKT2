"""
Verification Suite for Single-Part Master Overhaul:
1. Hyper-Realistic Human Voice Engine (Spoken-Colloquial Phonetics, Natural Prosody, Multi-Bot Voice Resolver, Smartphone Mic DSP)
2. 100% Realistic Human Selfie Engine (Zero Watermarks Dual-Layer Guard, Persistent Per-Bot Visual DNA, Locked Room + Dynamic Expression/Angle/Pose/Outfit Engine)
"""

import asyncio
import os
import py_compile
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


FILES_TO_COMPILE = [
    "bot_factory/models.py",
    "bot_factory/factory_manager.py",
    "bot_factory/multi_bot_dispatcher.py",
    "aether_human_core/multimodal_engine/acoustic_voice/realistic_voice_generator.py",
    "aether_human_core/multimodal_engine/acoustic_voice/voice_intent_enforcer.py",
    "aether_human_core/multimodal_engine/visual_identity/face_lock_pipeline.py",
    "aether_human_core/multimodal/__init__.py",
    "aether_human_core/multimodal/realistic_voice.py",
    "aether_human_core/multimodal/image_generator.py",
    "aether_human_core/cognitive_engine/orchestrator.py",
    "aether_human_core/telegram_client/handlers/media_handler.py",
    "aether_human_core/telegram_client/handlers/group_handler.py",
]


def test_syntax_compilation() -> None:
    print("=== [1/6] Testing Python Syntax Compilation ===")
    for rel_path in FILES_TO_COMPILE:
        full_path = PROJECT_ROOT / rel_path
        assert full_path.exists(), f"Missing file: {full_path}"
        py_compile.compile(str(full_path), doraise=True)
        print(f"  [OK] Compiled: {rel_path}")


def test_spoken_colloquial_phonetic_preprocessor() -> None:
    print("\n=== [2/6] Testing Spoken-Colloquial Phonetic Pre-Processor ===")
    from aether_human_core.multimodal.realistic_voice import clean_for_human_speech

    raw_text = "ألوووو يااااه يا عيوووني آآآآه أنا مبسوط قوي ودائماً معاك ثواني 😂🔥 https://example.com **تمام**"
    cleaned = clean_for_human_speech(raw_text, dialect="egyptian")
    print(f"  Raw:     {raw_text}")
    print(f"  Cleaned: {cleaned}")

    assert "ألووو" not in cleaned and "ألو" in cleaned, f"Failed to collapse 'ألوووو': {cleaned}"
    assert "يااا" not in cleaned and "ياه" in cleaned, f"Failed to collapse 'يااااه': {cleaned}"
    assert "عيووو" not in cleaned and "عيوني" in cleaned, f"Failed to collapse 'عيوووني': {cleaned}"
    assert "آآآ" not in cleaned and "آه" in cleaned, f"Failed to collapse 'آآآآه': {cleaned}"
    assert "أوي" in cleaned, f"Failed phonetic conversion 'قوي' -> 'أوي': {cleaned}"
    assert "دايماً" in cleaned, f"Failed phonetic conversion 'دائماً' -> 'دايماً': {cleaned}"
    assert "سواني" in cleaned, f"Failed phonetic conversion 'ثواني' -> 'سواني': {cleaned}"
    assert "😂" not in cleaned and "🔥" not in cleaned, f"Failed emoji stripping: {cleaned}"
    assert "https://" not in cleaned, f"Failed URL stripping: {cleaned}"
    assert "**" not in cleaned, f"Failed markdown stripping: {cleaned}"
    assert ("،" in cleaned or "..." in cleaned), f"Failed breathing pause injection: {cleaned}"
    print("  [OK] Spoken-colloquial phonetic pre-processor passed all checks!")


def test_natural_prosody_and_voice_resolver() -> None:
    print("\n=== [3/6] Testing Natural Prosody & Multi-Bot Voice Resolver ===")
    from aether_human_core.multimodal.realistic_voice import RealisticVoice

    rv = RealisticVoice()
    for mood in ["ENERGETIC", "HAPPY", "PLAYFUL", "CALM", "TIRED", "SLEEPY", "SAD"]:
        rate_str, pitch_str = rv.compute_voice_modulation(mood_state=mood, energy_level=0.75 if mood != "SLEEPY" else 0.25)
        rate_val = int(rate_str.replace("%", "").replace("+", ""))
        pitch_val = int(pitch_str.replace("Hz", "").replace("+", ""))
        assert -3 <= rate_val <= 6, f"Rate out of natural human range [-3%, +6%]: {rate_str}"
        assert -2 <= pitch_val <= 2, f"Pitch out of natural human range [-2Hz, +2Hz]: {pitch_str}"
        print(f"  [OK] Mood={mood:<10} -> Rate={rate_str:<4} Pitch={pitch_str:<5}")

    # Test distinct bot voices
    bots_to_check = [
        ("master_omar_official", "عمر", "male", "egyptian"),
        ("userbot_8656468004", "ريمي", "female", "egyptian"),
        ("bot_1793564427271", "مريم", "female", "egyptian"),
        ("bot_1793633133088", "ماسه", "female", "iraqi"),
        ("bot_1793709138213", "مصطفي", "male", "egyptian"),
        ("bot_1793725567511", "ملوكة", "female", "egyptian"),
    ]
    for bot_id, name, gender, dialect in bots_to_check:
        edge_v, gemini_v = rv.resolve_bot_voice(
            dialect_code=dialect,
            gender=gender,
            bot_id=bot_id,
            bot_name=name,
        )
        print(f"  [OK] Bot={name:<6} ({gender:<6}, {dialect:<8}) -> Edge={edge_v:<20} Gemini={gemini_v}")
        if gender == "female":
            assert any(f in edge_v for f in ["Salma", "Rana", "Zariyah", "Amany", "Layla", "Mouna", "Noura"]), (
                f"Female bot {name} assigned male voice {edge_v}"
            )
        else:
            assert any(m in edge_v for m in ["Shakir", "Bassel", "Hamed", "Laith", "Rami", "Hedi", " Abdullah"]), (
                f"Male bot {name} assigned female voice {edge_v}"
            )


async def test_voice_note_generation_and_dsp() -> None:
    print("\n=== [4/6] Testing End-to-End Voice Note Synthesis & Smartphone Mic DSP ===")
    from aether_human_core.multimodal.realistic_voice import voice_generator

    ogg_path, waveform, duration = await voice_generator.generate_voice_note(
        text="ألوووو يا صاحبي عامل إيه والله وحشتني قوي ثواني وأكلمك",
        mood_state="HAPPY",
        energy_level=0.82,
        dialect_code="egyptian",
        gender="male",
        bot_id="master_omar_official",
        bot_name="عمر",
        location_context="BEDROOM",
    )
    assert ogg_path is not None and os.path.exists(ogg_path), "Male voice note file was not created!"
    file_size = os.path.getsize(ogg_path)
    assert file_size > 1500, f"Voice note too small ({file_size} bytes)"
    assert len(waveform) > 0, "Waveform bytes empty!"
    print(f"  [OK] Male Voice Note ('عمر'): {ogg_path} ({file_size} bytes, {duration:.2f}s, waveform={len(waveform)} bytes)")

    ogg_path_f, waveform_f, duration_f = await voice_generator.generate_voice_note(
        text="يااااه يا قلبي والله مبسوطة قوي إني سمعت صوتك النهاردة",
        mood_state="PLAYFUL",
        energy_level=0.80,
        dialect_code="egyptian",
        gender="female",
        bot_id="userbot_8656468004",
        bot_name="ريمي",
        location_context="CAFE",
    )
    assert ogg_path_f is not None and os.path.exists(ogg_path_f), "Female voice note file was not created!"
    file_size_f = os.path.getsize(ogg_path_f)
    assert file_size_f > 1500, f"Female voice note too small ({file_size_f} bytes)"
    print(f"  [OK] Female Voice Note ('ريمي'): {ogg_path_f} ({file_size_f} bytes, {duration_f:.2f}s, waveform={len(waveform_f)} bytes)")


def test_visual_dna_and_photo_variation_engine() -> None:
    print("\n=== [5/6] Testing Persistent Per-Bot Visual DNA & PhotoVariationEngine ===")
    from bot_factory.factory_manager import bot_factory, MultiBotFactoryService
    from bot_factory.models import BotGender
    from aether_human_core.multimodal.image_generator import face_lock_pipeline, photo_variation_engine

    all_bots = bot_factory.list_all_bots()
    seen_dnas = set()
    seen_seeds = set()
    for bot in all_bots:
        assert bot.visual_dna, f"Bot {bot.instance_id} ({bot.name}) has empty visual_dna!"
        assert bot.base_identity_seed > 0, f"Bot {bot.instance_id} has invalid base_identity_seed!"
        assert bot.visual_dna not in seen_dnas, f"Duplicate visual_dna detected on {bot.instance_id}!"
        assert bot.base_identity_seed not in seen_seeds, f"Duplicate base_identity_seed on {bot.instance_id}!"
        seen_dnas.add(bot.visual_dna)
        seen_seeds.add(bot.base_identity_seed)
        print(
            f"  [OK] Locked DNA for {bot.name:<6} ({bot.instance_id}): "
            f"seed={bot.base_identity_seed}, dna='{bot.visual_dna[:65]}...'"
        )

    # Verify auto-generation for a brand new hypothetical sub-bot
    new_dna, new_seed = MultiBotFactoryService.generate_unique_visual_dna(
        instance_id="bot_future_test_999",
        name="كريم",
        gender=BotGender.MALE,
        age=26,
        origin_location="Alexandria, Egypt",
        primary_dialect="egyptian",
    )
    assert new_dna and new_dna not in seen_dnas
    assert new_seed > 0 and new_seed not in seen_seeds
    print(f"  [OK] Auto-generated DNA for future sub-bot 'كريم': seed={new_seed}, dna='{new_dna[:65]}...'")

    # Verify 5 consecutive photo prompts in the same room for Omar never repeat expression, angle, pose, or outfit
    expressions_used = []
    angles_used = []
    poses_used = []
    outfits_used = []
    for i in range(5):
        prompt, seed, bot_key, lighting_period = face_lock_pipeline.assemble_prompt(
            mood_str="HAPPY",
            bot_id="master_omar_official",
            persona_name="عمر",
            gender="male",
        )
        assert "Raw, unedited, candid amateur front-camera smartphone selfie, shot on iPhone 15" in prompt
        assert "NEGATIVE CONSTRAINTS:" in prompt
        assert "24-year-old Egyptian man" in prompt
        state = photo_variation_engine._state[bot_key][-1]
        assert state["expression"] not in expressions_used, f"Repeated expression on shot {i+1}!"
        assert state["camera_angle"] not in angles_used, f"Repeated camera_angle on shot {i+1}!"
        assert state["pose"] not in poses_used, f"Repeated pose on shot {i+1}!"
        assert state["outfit_detail"] not in outfits_used, f"Repeated outfit_detail on shot {i+1}!"
        expressions_used.append(state["expression"])
        angles_used.append(state["camera_angle"])
        poses_used.append(state["pose"])
        outfits_used.append(state["outfit_detail"])
        print(
            f"  [OK] Shot #{i+1} (seed={seed}): expr='{state['expression'][:32]}...', "
            f"angle='{state['camera_angle'][:28]}...'"
        )


async def test_watermark_guard_and_live_selfie_generation() -> None:
    print("\n=== [6/7] Testing Dual-Layer Watermark Guard & Smartphone Sensor Post-Processing ===")
    from aether_human_core.multimodal.image_generator import face_lock_pipeline

    # First test Layer-2 Pillow post-processing deterministically on a synthetic image with a bottom-right watermark
    test_img = Image.new("RGB", (896, 1152), color=(110, 120, 130))
    # Draw bright white watermark block in the bottom 5% right corner (where pollinations stamps its logo)
    for y in range(int(1152 * 0.955), 1152):
        for x in range(int(896 * 0.70), 896):
            test_img.putpixel((x, y), (255, 255, 255))

    tmp_watermark_test = os.path.join(face_lock_pipeline.output_dir, "test_watermark_guard.jpg")
    face_lock_pipeline.post_process_smartphone_selfie(
        raw_image=_pil_to_bytes(test_img),
        dest_path=tmp_watermark_test,
        lighting_period="NIGHT",
    )
    with Image.open(tmp_watermark_test) as out_img:
        assert out_img.size == (896, 1152), f"Expected (896, 1152), got {out_img.size}"
        # Verify bottom-right corner no longer has the bright white watermark (255, 255, 255)
        corner_pixel = out_img.getpixel((885, 1145))
        assert corner_pixel[0] < 200 and corner_pixel[1] < 200 and corner_pixel[2] < 200, (
            f"Watermark in bottom-right corner was NOT cropped! Corner pixel={corner_pixel}"
        )
        print(f"  [OK] Layer-2 Watermark Crop Guard + CMOS Sensor Grain verified (size={out_img.size}, corner_pixel={corner_pixel})")
    try:
        os.remove(tmp_watermark_test)
    except Exception:
        pass

    # Now test live end-to-end photo generation for Remy (female)
    photo_path = await face_lock_pipeline.generate_photo(
        requester_name="ECENN",
        custom_mood="HAPPY",
        bot_id="userbot_8656468004",
        persona_name="ريمي",
        gender="female",
    )
    assert photo_path and os.path.exists(photo_path), "Live selfie generation returned no file!"
    with Image.open(photo_path) as live_img:
        assert live_img.size == (896, 1152), f"Live selfie size mismatch: {live_img.size}"
        print(f"  [OK] Live Selfie Generated & Post-Processed for 'ريمي': {photo_path} (size={live_img.size}, {os.path.getsize(photo_path)} bytes)")


async def test_new_bot_mtproto_fallback_and_arbiter() -> None:
    print("\n=== [7/7] Testing New Bot ('باتو') GroupArbiter & Direct Telethon MTProto Connection ===")
    from bot_factory.group_arbiter import group_arbiter
    from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher

    # 1. Verify GroupArbiter recognizes 'باتو' when called by name, and ignores 'بات'
    d_bato = await group_arbiter.elect_reply_turn(
        chat_id=-100999888777,
        message_id=9001,
        sender_id=8287744705,
        message_text="يا باتو تعال لهون",
        reply_to_from_id=None,
        reply_to_msg_id=None,
        is_group=True,
        requesting_bot_id="bot_1793840547026",
    )
    assert d_bato.should_reply and d_bato.winner_bot_id == "bot_1793840547026", (
        f"Expected 'باتو' to win when addressed as 'يا باتو', got: {d_bato}"
    )
    print(f"  [OK] GroupArbiter elected 'باتو' on 'يا باتو تعال لهون': {d_bato}")

    d_bat_only = await group_arbiter.elect_reply_turn(
        chat_id=-100999888777,
        message_id=9002,
        sender_id=8287744705,
        message_text="يا بات عامل ايه",
        reply_to_from_id=None,
        reply_to_msg_id=None,
        is_group=True,
        requesting_bot_id="bot_1793840547026",
    )
    assert not d_bat_only.should_reply, f"'باتو' should NOT trigger on 'يا بات': {d_bat_only}"
    print(f"  [OK] GroupArbiter kept 'باتو' silent when 'يا بات' (different bot) was called: {d_bat_only}")

    # 2. Verify Direct Telethon MTProto Fallback connects 'باتو' (9052129106:...) and executes getMe
    token_bato = "9052129106:AAFnotyLBLkhaFp-BYsCnLNvNJxIGdmTElE"
    ok_mt = await multi_bot_dispatcher.ensure_mtproto_for_token(token_bato)
    assert ok_mt, "Failed to connect 'باتو' via Direct Telethon MTProto!"
    http = await multi_bot_dispatcher._get_http()
    me_resp = await http.get(f"https://api.telegram.org/bot{token_bato}/getMe")
    assert me_resp.status_code == 200 and me_resp.json().get("ok"), f"MTProto getMe shim failed: {me_resp.text}"
    print(f"  [OK] Direct MTProto Shim getMe for 'باتو': {me_resp.json()}")
    multi_bot_dispatcher.stop_all()


def _pil_to_bytes(img: Image.Image) -> bytes:
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


async def main() -> None:
    test_syntax_compilation()
    test_spoken_colloquial_phonetic_preprocessor()
    test_natural_prosody_and_voice_resolver()
    await test_voice_note_generation_and_dsp()
    test_visual_dna_and_photo_variation_engine()
    await test_watermark_guard_and_live_selfie_generation()
    await test_new_bot_mtproto_fallback_and_arbiter()
    print("\n======================================================================")
    print("ALL VOICE, SELFIE & MTPROTO SUB-BOT TESTS PASSED 100%!")
    print("======================================================================")


if __name__ == "__main__":
    asyncio.run(main())
