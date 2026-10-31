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


async def main():
    print("Testing Owner 100% Affinity Lock & Interactive Profile Menu...")

    owner_id = settings.super_admin_ids_list[0]
    normal_id = 9988776655

    async with db_manager.session() as session:
        repo = UserRepository(session)

        # 1. Fetch or create owner
        owner_user = await repo.get_or_create(owner_id, first_name="Owner Master")
        assert owner_user.affinity_score == 100.0, f"Owner affinity should be 100.0, got {owner_user.affinity_score}"
        assert owner_user.relationship_tier == "EXCLUSIVE_PARTNER"

        # Attempt to reduce owner affinity
        updated_owner = await repo.update_affinity_scores(owner_id, delta_affinity=-50.0, delta_trust=-30.0)
        assert updated_owner.affinity_score == 100.0, "Owner affinity was reduced! Should remain 100.0"
        assert updated_owner.trust_score == 100.0, "Owner trust was reduced! Should remain 100.0"
        print("  ✓ Owner affinity immutably locked at 100.0/100 and immune to deductions.")

        # 2. Normal user test
        normal_user = await repo.get_or_create(normal_id, first_name="Friendly Tester")
        initial_score = normal_user.affinity_score
        updated_normal = await repo.update_affinity_scores(normal_id, delta_affinity=5.5)
        assert updated_normal.affinity_score == initial_score + 5.5
        print(f"  ✓ Normal user affinity properly adjusted: {initial_score} -> {updated_normal.affinity_score}")

    # 3. Test render_main_dashboard contains affinity score and tier
    dash_text, dash_markup = await telegram_menu.render_main_dashboard(owner_id, "Owner Master")
    assert "رصيد معزتك وتفضيلك" in dash_text
    assert "100.0/100" in dash_text
    assert "menu:user_affinity" in str(dash_markup)
    print("  ✓ Main Dashboard displays affinity bar and dedicated button.")

    # 4. Test render_user_affinity_profile for owner
    prof_text, prof_markup = await telegram_menu.render_user_affinity_profile(owner_id, "Owner Master")
    assert "حصانة مالك وسيد النظام المطلقة" in prof_text
    assert "100.0 / 100.0" in prof_text
    assert "act:refresh_affinity" in str(prof_markup)
    print("  ✓ Owner profile displays Master Immunity and full 100% bars.")

    # 5. Test render_user_affinity_profile for normal user
    u_prof_text, u_prof_markup = await telegram_menu.render_user_affinity_profile(normal_id, "Friendly Tester")
    assert "حصانة مالك وسيد النظام المطلقة" not in u_prof_text
    assert "تفاصيل أبعاد الرصيد والمشاعر" in u_prof_text
    print("  ✓ Normal user profile displays detailed breakdown without owner badge.")

    # 6. Test handle_callback for menu:user_affinity and act:refresh_affinity
    cb_text, cb_markup, alert, trigger = await telegram_menu.handle_callback("menu:user_affinity", owner_id, "Owner Master")
    assert cb_text is not None
    assert "بطاقة المكانة والرصيد العاطفي" in cb_text

    cb_text2, cb_markup2, alert2, _ = await telegram_menu.handle_callback("act:refresh_affinity", owner_id, "Owner Master")
    assert alert2 == "💖 تم تحديث تفاصيل مكانتك ورصيدك عند عمر بنجاح!"
    print("  ✓ Callback handlers for user_affinity and refresh_affinity passed.")

    print("\n🎉 ALL AFFINITY & MENU CHECKS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(main())
