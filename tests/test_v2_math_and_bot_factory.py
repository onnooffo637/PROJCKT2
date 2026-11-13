"""
Test Suite for Math Formatter, Sovereign King Claim, and Multi-Bot Factory (V2.0).
"""

import asyncio
import os
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aether_human_core.cognitive_engine.math_formatter import math_formatter
from core_config.sovereignty_rules import sovereignty_guard, SovereigntyProtocolService
from bot_factory.models import BotPlatformType, BotGender
from bot_factory.persona_templates import template_registry
from bot_factory.factory_manager import bot_factory


class TestMathAndBotFactory(unittest.IsolatedAsyncioTestCase):

    # -------------------------------------------------------------
    # 1. Human Math Formatter Tests
    # -------------------------------------------------------------
    def test_human_math_formatter(self):
        print("\n[TEST 1] Testing Human Math Formatter & LaTeX Sanitizer...")
        raw_latex = (
            r"حل المعادلة: \( x^2 - 5x + 6 = 0 \) باستخدام القانون: "
            r"\[ x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a} \] حيث \(\pi \approx 3.14\) و \(x_1 \le x_2\)"
        )
        formatted = math_formatter.format_math_text(raw_latex)

        # Asserts: No backslashes or raw LaTeX syntax remain
        self.assertNotIn(r"\(", formatted)
        self.assertNotIn(r"\)", formatted)
        self.assertNotIn(r"\[", formatted)
        self.assertNotIn(r"\]", formatted)
        self.assertNotIn(r"\frac", formatted)
        self.assertNotIn(r"\sqrt", formatted)
        self.assertNotIn(r"\pm", formatted)
        self.assertNotIn(r"\approx", formatted)

        # Unicode math symbols must be present
        self.assertIn("²", formatted)
        self.assertIn("√", formatted)
        self.assertIn("±", formatted)
        self.assertIn("π", formatted)
        self.assertIn("≈", formatted)
        self.assertIn("≤", formatted)
        print("  ✓ Clean Human-Readable Math Output:\n" + formatted)

    # -------------------------------------------------------------
    # 2. Sovereign King Claim & Admin Differentiation Tests
    # -------------------------------------------------------------
    def test_sovereign_king_claim_and_admin_differentiation(self):
        print("\n[TEST 2] Testing Sovereign King Claim & Admin Differentiation...")
        admin1_id = 8287744705
        admin2_id = 8697154015
        stranger_id = 123456789

        # Stranger cannot claim King identity
        ok_stranger, msg_stranger = sovereignty_guard.claim_king_identity(stranger_id)
        self.assertFalse(ok_stranger)
        print("  ✓ Stranger successfully blocked from claiming King title.")

        # Admin 1 claims King identity
        ok1, msg1 = sovereignty_guard.claim_king_identity(admin1_id)
        self.assertTrue(ok1)
        self.assertTrue(sovereignty_guard.is_king(admin1_id))
        self.assertFalse(sovereignty_guard.is_other_admin(admin1_id))

        # Admin 2 is recognized as the other admin, not the King
        self.assertTrue(sovereignty_guard.is_other_admin(admin2_id))
        self.assertFalse(sovereignty_guard.is_king(admin2_id))

        # Salutation check: King gets Zero/Abdulrahman title
        king_salute = sovereignty_guard.get_salutation_for_user(admin1_id, "عبد الرحمن")
        self.assertIn("زيرو", king_salute)
        self.assertIn("عبد الرحمن", king_salute)
        print(f"  ✓ King Salutation: '{king_salute}'")

        # Admin 2 salutation MUST NOT contain Zero or Abdulrahman
        admin2_salute = sovereignty_guard.get_salutation_for_user(admin2_id, "أحمد")
        self.assertNotIn("زيرو", admin2_salute)
        self.assertNotIn("عبد الرحمن", admin2_salute)
        self.assertIn("باشمهندس", admin2_salute)
        print(f"  ✓ Co-Admin Salutation (Excludes King titles): '{admin2_salute}'")

    # -------------------------------------------------------------
    # 3. Multi-Bot Factory & Gender Switching Tests
    # -------------------------------------------------------------
    def test_multi_bot_factory_lifecycle(self):
        print("\n[TEST 3] Testing Multi-Bot Factory Lifecycle & Gender Shifts...")
        # 1. Verify Templates
        templates = template_registry.list_all_templates()
        self.assertGreaterEqual(len(templates), 6)
        codes = [t["template_code"] for t in templates]
        self.assertIn("MASA_TECH", codes)
        self.assertIn("MARIAM_HEALER", codes)
        self.assertIn("LAYLA_POET", codes)
        self.assertIn("SEIF_ATHLETE", codes)
        self.assertIn("KARIM_STRATEGIST", codes)
        print(f"  ✓ {len(templates)} Character Templates loaded in Factory.")

        # 2. Create Female Bot (Masa)
        ok_create, msg_create, masa_bot = bot_factory.create_bot(
            instance_id="bot_masa_test",
            name="ماسة",
            bot_type=BotPlatformType.OFFICIAL_BOT,
            token_or_session="111222333:TEST_TOKEN_MASA",
            gender=BotGender.FEMALE,
            template_code="MASA_TECH",
        )
        self.assertTrue(ok_create)
        self.assertEqual(masa_bot.gender, BotGender.FEMALE)
        self.assertIn("أنتِ 'ماسة'", masa_bot.system_prompt)
        print(f"  ✓ Spawned Female Bot «{masa_bot.name}»: Gender = {masa_bot.gender.value}")

        # 3. Toggle Gender (Convert Masa to Male)
        ok_toggle, msg_toggle = bot_factory.set_bot_gender("bot_masa_test", BotGender.MALE)
        self.assertTrue(ok_toggle)
        updated_bot = bot_factory.get_bot("bot_masa_test")
        self.assertEqual(updated_bot.gender, BotGender.MALE)
        self.assertIn("أنت 'ماسة'", updated_bot.system_prompt)
        print(f"  ✓ Toggled Gender to MALE: {msg_toggle}")

        # 4. Toggle Gender Back to Female
        ok_back, msg_back = bot_factory.set_bot_gender("bot_masa_test", BotGender.FEMALE)
        self.assertTrue(ok_back)
        updated_bot2 = bot_factory.get_bot("bot_masa_test")
        self.assertEqual(updated_bot2.gender, BotGender.FEMALE)
        self.assertIn("أنتِ 'ماسة'", updated_bot2.system_prompt)
        print(f"  ✓ Toggled Gender back to FEMALE: {msg_back}")

        # 5. Clean up test bot
        del_ok, del_msg = bot_factory.delete_bot("bot_masa_test")
        self.assertTrue(del_ok)
        print(f"  ✓ Test instance safely cleaned from factory.")


if __name__ == "__main__":
    unittest.main()

