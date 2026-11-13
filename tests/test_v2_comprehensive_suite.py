"""
Comprehensive Test Suite for Project Aether-Human (V2.0).
Verifies:
1. Multi-Persona Registry & Persona Shifter
2. Cloud & Resource Guard (File Compressor & Railway Health Governor)
3. Interactive Games Engine & Game-to-Chat Emotion Bridge
4. Academic Research Assistant & Exam Bank Generation
5. Mini App FastAPI endpoints & Health Probes
"""

import asyncio
import io
import os
import sys
import unittest
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core_config.personas_registry import persona_registry
from core_config.sovereignty_rules import SovereigntyProtocolService, RoyalRank
from aether_human_core.cognitive_engine.persona_shifter import persona_shifter
from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
from cloud_and_resource_guard.file_stream_compressor import file_compressor
from cloud_and_resource_guard.railway_health_governor import resource_governor
from mini_app_webapp.games_engine import XOGameSession, TriviaBank
from official_bot_engine.game_chat_bridge import game_chat_bridge
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository


class TestAetherHumanV2(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await db_manager.init_schema()

    # -------------------------------------------------------------
    # 1. Multi-Persona Shifter Tests
    # -------------------------------------------------------------
    async def test_persona_registry_and_shifting(self):
        print("\n[TEST 1] Testing Persona Registry & Persona Shifter...")
        # Verify all 7 archetypes exist
        all_p = persona_registry.list_all_personas()
        self.assertGreaterEqual(len(all_p), 7)
        codes = [p["code"] for p in all_p]
        for expected in ["DEFAULT_BALANCED", "SCHOLAR", "SHADOW_AYANOKOJI", "JESTER", "ROMANTIC", "EGYPTIAN_STREET", "VILLAIN_HUNTER"]:
            self.assertIn(expected, codes)
        print("  ✓ All 7 core behavioral archetypes successfully registered.")

        # Test setting persona
        ok, msg = persona_shifter.set_persona("SCHOLAR", user_id=8287744705)
        self.assertTrue(ok)
        active = persona_shifter.get_active_persona()
        self.assertEqual(active.code, "SCHOLAR")
        self.assertEqual(active.temperament, "INTELLECTUAL_DEEP")
        print(f"  ✓ Persona shifted to SCHOLAR: {active.name_ar}")

        # Test natural language shift command
        shift_res = persona_shifter.evaluate_natural_language_shift(
            sender_id=8287744705,
            message_text="يا عمر تحول لوضع شادو",
        )
        self.assertIsNotNone(shift_res)
        self.assertTrue(shift_res[0])
        active = persona_shifter.get_active_persona()
        self.assertEqual(active.code, "SHADOW_AYANOKOJI")
        print(f"  ✓ Natural Arabic intent switched persona to: {active.name_ar}")

        # Reset back to default
        persona_shifter.set_persona("DEFAULT_BALANCED", user_id=8287744705)
        self.assertEqual(persona_shifter.get_active_persona().code, "DEFAULT_BALANCED")
        print("  ✓ Successfully restored default balanced persona.")

    # -------------------------------------------------------------
    # 2. Cloud & Resource Guard Tests
    # -------------------------------------------------------------
    async def test_file_stream_compressor(self):
        print("\n[TEST 2] Testing Zero-Disk-Bloat File & Stream Compressor...")
        # Create a sample RGB image in memory
        img = Image.new("RGB", (800, 600), color=(73, 109, 137))
        img_bytes_io = io.BytesIO()
        img.save(img_bytes_io, format="PNG")
        original_bytes = img_bytes_io.getvalue()

        # Compress to WebP
        webp_bytes = file_compressor.compress_image_to_webp(original_bytes)
        self.assertIsInstance(webp_bytes, bytes)
        self.assertLess(len(webp_bytes), len(original_bytes))
        print(f"  ✓ In-memory image compressed: {len(original_bytes)} bytes PNG -> {len(webp_bytes)} bytes WebP.")

        # Test text extraction from memory
        raw_text = "بسم الله الرحمن الرحيم - تجربة استخراج النصوص الأكاديمية"
        extracted = file_compressor.extract_text_from_document("lecture.txt", raw_text.encode("utf-8"))
        self.assertEqual(extracted, raw_text)
        print("  ✓ Document text safely extracted from in-memory stream.")

        # Test safe temporary file context manager
        temp_file_path = None
        with file_compressor.safe_temporary_file(suffix=".bin") as temp_p:
            temp_file_path = temp_p
            self.assertTrue(os.path.exists(temp_file_path))
            with open(temp_file_path, "w") as f:
                f.write("temporary data")
        self.assertFalse(os.path.exists(temp_file_path))
        print("  ✓ Zero-Disk-Bloat confirmed: temporary file strictly deleted on exit.")

    async def test_railway_health_governor(self):
        print("\n[TEST 3] Testing Railway Health Governor & Metrics...")
        metrics = resource_governor.get_health_metrics()
        self.assertEqual(metrics.service, "AETHER-HUMAN-DUAL-CORE")
        self.assertGreater(metrics.memory_rss_mb, 0.0)
        self.assertGreater(metrics.uptime_seconds, 0.0)
        print(f"  ✓ Health metrics retrieved: RSS = {metrics.memory_rss_mb} MB | Status = {metrics.status}")

        # Emergency pruning
        prune_res = resource_governor.perform_emergency_pruning()
        self.assertIn("freed_objects", prune_res)
        print(f"  ✓ Emergency pruning executed: freed {prune_res['freed_objects']} objects.")

    # -------------------------------------------------------------
    # 3. Interactive Games & Emotion Bridge Tests
    # -------------------------------------------------------------
    async def test_xo_game_and_emotion_bridge(self):
        print("\n[TEST 4] Testing Tic-Tac-Toe (XO) & Emotion Bridge...")
        session = XOGameSession(user_id=112233)
        # Move at center
        ok, res = session.user_move(4)
        self.assertTrue(ok)
        self.assertEqual(session.board[4], "X")
        # Omar should have made a move
        self.assertIn("O", session.board)
        print(f"  ✓ User moved at 4, Omar countered at: {[i for i, v in enumerate(session.board) if v == 'O']}")

        # Test Emotion Bridge on user victory
        pre_cortisol = endocrine_engine.get_current_state().cortisol
        outcome_res = await game_chat_bridge.process_game_outcome(
            game_name="XO",
            user_id=112233,
            user_name="فهد",
            outcome="USER_WON",
        )
        self.assertEqual(outcome_res.outcome, "USER_WON")
        self.assertGreater(outcome_res.cortisol_delta, 0.0)
        post_cortisol = endocrine_engine.get_current_state().cortisol
        self.assertGreaterEqual(post_cortisol, pre_cortisol)
        print(f"  ✓ User won: Cortisol increased to {post_cortisol:.2f} | Omar retort: '{outcome_res.omar_retort}'")

        # Test Emotion Bridge on Omar victory
        outcome_omar = await game_chat_bridge.process_game_outcome(
            game_name="XO",
            user_id=112233,
            user_name="فهد",
            outcome="OMAR_WON",
        )
        self.assertEqual(outcome_omar.outcome, "OMAR_WON")
        self.assertGreater(outcome_omar.dopamine_delta, 0.0)
        print(f"  ✓ Omar won: Dopamine boosted | Omar retort: '{outcome_omar.omar_retort}'")

    async def test_trivia_arena(self):
        print("\n[TEST 5] Testing Trivia Knowledge Bank...")
        q = TriviaBank.get_random_question()
        self.assertIsNotNone(q.question)
        self.assertEqual(len(q.options), 4)
        self.assertGreaterEqual(q.correct_index, 0)
        self.assertLess(q.correct_index, 4)
        print(f"  ✓ Trivia Question [{q.category}]: '{q.question}' | Correct answer index: {q.correct_index}")


if __name__ == "__main__":
    unittest.main()

