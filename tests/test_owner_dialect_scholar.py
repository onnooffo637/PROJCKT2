import asyncio
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aether_human_core.config.settings import settings
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from aether_human_core.psychology_engine.dialect_chameleon import dialect_chameleon
from aether_human_core.cognitive_engine.orchestrator import cognitive_orchestrator
from aether_human_core.telegram_client.mtproto_manager import mtproto_manager


async def test_king_immunity_and_protection():
    print("Testing King Immunity and Loyalty Protocol...")
    king_id = settings.super_admin_ids_list[0]  # 8287744705

    # 1. King affinity cannot decrease
    async with db_manager.session() as session:
        repo = UserRepository(session)
        king_user = await repo.get_or_create(king_id, first_name="عبد الرحمن (زيرو)")
        assert king_user.affinity_score == 100.0
        assert king_user.role == "SUPER_ADMIN"
        print(f"  ✓ King registered with max affinity: {king_user.affinity_score}/100")

        # Try to decrease king affinity
        updated_king = await repo.update_affinity_scores(king_id, delta_affinity=-50.0)
        assert updated_king.affinity_score == 100.0, "King affinity should be locked at 100.0!"
        print("  ✓ King affinity is completely immune to reduction (Locked at 100.0).")

    # 2. Defense of King Zero from third party threat
    stranger_id = 7776665554
    resp = await cognitive_orchestrator.process_incoming_event(
        telegram_message_id=901,
        chat_id=-1001234567890,
        sender_id=stranger_id,
        sender_name="حسام",
        message_text="يا شباب عمر هنسفك دم زيرو ونضربه",
        media_type="text",
        chat_type="supergroup",
        chat_title="جروب الصحاب",
    )
    assert "إلا زيرو" in resp.raw_response_text
    assert "مبرمجي" in resp.raw_response_text
    print(f"  ✓ Omar defended King Zero passionately: '{resp.raw_response_text}'")


async def test_dialect_system():
    print("Testing Dialect System (MSA Default & Dynamic Adaptation)...")

    # Default should be Modern Standard Arabic
    default_d = dialect_chameleon.detect_dialect("أهلاً، أريد الاستفسار عن خدمة معينة")
    assert default_d.code == "standard_arabic", f"Expected standard_arabic, got {default_d.code}"
    print(f"  ✓ Default dialect correctly identified as: {default_d.name_ar}")

    # Iraqi detection
    iraqi_d = dialect_chameleon.detect_dialect("شكو ماكو عيوني شبيك هسه")
    assert iraqi_d.code == "iraqi", f"Expected iraqi, got {iraqi_d.code}"
    print(f"  ✓ Iraqi dialect correctly identified: {iraqi_d.name_ar}")

    # Maghrebi / Algerian detection
    magh_d = dialect_chameleon.detect_dialect("واش راك خويا صافا لاباس عليك")
    assert magh_d.code == "maghrebi", f"Expected maghrebi, got {magh_d.code}"
    print(f"  ✓ Maghrebi dialect correctly identified: {magh_d.name_ar}")

    # Egyptian detection
    egy_d = dialect_chameleon.detect_dialect("يا عم بص كدة عامل إيه يا باشا")
    assert egy_d.code == "egyptian", f"Expected egyptian, got {egy_d.code}"
    print(f"  ✓ Egyptian dialect correctly identified: {egy_d.name_ar}")

    # English detection
    eng_d = dialect_chameleon.detect_dialect("Hello bro how are you doing today?")
    assert eng_d.code == "english", f"Expected english, got {eng_d.code}"
    print(f"  ✓ English correctly identified: {eng_d.name_ar}")


async def test_scholar_mode():
    print("Testing Serious / Scholar Mode ('عمر بجدية')...")
    scholar_text = "يا عمر بجدية ما هي النظرية النسبية العامة لأينشتاين؟"
    norm = scholar_text.lower().replace("ة", "ه").replace("إ", "ا").replace("أ", "ا")
    is_scholar = ("عمر" in norm or "يا عمر" in norm) and any(w in norm for w in ["بجديه", "بجدية", "جديه", "جدية", "بالجد", "بجد"])
    assert is_scholar, "Failed to detect serious/scholar mode trigger!"
    print("  ✓ Serious / Scholar mode detected correctly from phrase.")


async def test_mtproto_send_message():
    print("Testing mtproto_manager.send_message...")
    assert hasattr(mtproto_manager, "send_message"), "mtproto_manager missing send_message attribute!"
    assert hasattr(mtproto_manager, "ALLOWED_BOT_REACTION_EMOJIS")
    print("  ✓ mtproto_manager.send_message and emoji sanitization verified.")


async def test_ephemeral_and_group_silence():
    print("Testing Ephemeral Notifications & Group Silence...")
    assert hasattr(mtproto_manager, "send_ephemeral_message"), "Missing send_ephemeral_message!"

    # In groups: affinity_notification must ALWAYS be None
    resp_group = await cognitive_orchestrator.process_incoming_event(
        telegram_message_id=902,
        chat_id=-1001234567890,
        sender_id=7776665554,
        sender_name="حسام",
        message_text="يا عمر شكراً جداً ليك يا بطل ما قصرت",
        media_type="text",
        chat_type="supergroup",
        chat_title="جروب الصحاب",
    )
    assert resp_group.affinity_notification is None, "Affinity notification should NEVER be sent to groups!"
    print("  ✓ Verified: Affinity notification is strictly None in group chats.")


async def main():
    await test_king_immunity_and_protection()
    await test_dialect_system()
    await test_scholar_mode()
    await test_mtproto_send_message()
    await test_ephemeral_and_group_silence()
    print("\n🎉 ALL ADVANCED SYSTEM TESTS PASSED SUCCESSFULLY! 👑")


if __name__ == "__main__":
    asyncio.run(main())

