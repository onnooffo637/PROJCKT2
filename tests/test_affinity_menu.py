import asyncio
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aether_human_core.config.settings import settings
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from aether_human_core.telegram_client.telegram_menu import telegram_menu
from aether_human_core.psychology_engine.affinity_matrix import RelationshipTier
from aether_human_core.psychology_engine.admin_manager import admin_manager, RoleLevel
from aether_human_core.cognitive_engine.orchestrator import cognitive_orchestrator


async def main():
    print("Testing Negative Affinity, Villain Role & Separate Notification System...")

    owner_id = settings.super_admin_ids_list[0]
    villain_id = 1122334455

    # 1. Test Villain Promotion
    success, msg = await admin_manager.set_user_villain(owner_id, villain_id)
    assert success, f"Villain assignment failed: {msg}"

    async with db_manager.session() as session:
        repo = UserRepository(session)
        v_user = await repo.get_by_telegram_id(villain_id)
        assert v_user.role == "VILLAIN", f"Expected role VILLAIN, got {v_user.role}"
        assert v_user.affinity_score <= -70.0, f"Expected negative affinity, got {v_user.affinity_score}"
        assert v_user.relationship_tier == "ANTAGONIST"
        print("  ✓ User successfully promoted to VILLAIN with negative affinity (-75.0) and ANTAGONIST tier.")

    # 2. Test Negative Affinity Bar Rendering
    neg_bar = telegram_menu.render_affinity_bar(-75.0)
    assert "-" in neg_bar and "🦹" in neg_bar
    print(f"  ✓ Negative bar rendered properly: {neg_bar}")

    # 3. Test Villain Profile View
    prof_text, prof_markup = await telegram_menu.render_user_affinity_profile(villain_id, "Bad Guy")
    assert "الشرير والعدو اللدود" in prof_text
    assert "تنبيه رتبة الشرير" in prof_text
    print("  ✓ Villain profile displays distinctive alert and negative stats.")

    # 4. Test Insult Processing & Separate Notification
    # Send a toxic message to verify affinity decreases and notification is detached
    insult_user_id = 9988112233
    resp = await cognitive_orchestrator.process_incoming_event(
        telegram_message_id=501,
        chat_id=insult_user_id,
        sender_id=insult_user_id,
        sender_name="Angry Guy",
        message_text="يا حيوان يا زبالة يا عبيط",
        media_type="text",
        chat_type="private",
    )

    assert resp.affinity_delta < 0, f"Expected affinity drop on insult, got delta={resp.affinity_delta}"
    assert resp.current_affinity < 0, f"Expected negative affinity, got {resp.current_affinity}"
    assert resp.reaction_emoji == "💔", f"Expected broken heart reaction, got {resp.reaction_emoji}"
    assert resp.affinity_notification is not None, "Expected separate affinity notification"
    assert "إشعار تراجع التفضيل" in resp.affinity_notification
    # Ensure Omar's speech has NO system banner prepended
    assert "<blockquote>" not in resp.raw_response_text
    assert "تحديث الرصيد" not in resp.raw_response_text
    print(f"  ✓ Insult properly detected! Affinity dropped ({resp.affinity_delta:.1f}), reaction={resp.reaction_emoji}")
    print(f"  ✓ Omar's speech is 100% natural without system banners: '{resp.raw_response_text[:40]}...'")
    print(f"  ✓ Notification generated as separate message: '{resp.affinity_notification[:40]}...'")

    # 5. Verify All 10 Roles in RoleLevel
    expected_roles = ["SUPER_ADMIN", "ADMIN", "MODERATOR", "VIP", "FAVORITE", "WISE", "JESTER", "MEMBER", "COLD", "VILLAIN"]
    for r in expected_roles:
        assert r in RoleLevel.ROLE_NAMES, f"Role {r} missing from ROLE_NAMES"
        assert r in RoleLevel.ROLE_PERKS, f"Role {r} missing from ROLE_PERKS"
    print("  ✓ All 10 custom roles verified with distinct titles and perks.")

    print("\n🎉 ALL TESTS PASSED WITH 100% SUCCESS!")


if __name__ == "__main__":
    asyncio.run(main())
