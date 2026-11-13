# -*- coding: utf-8 -*-
"""
Verification Suite for PART 4 of 4:
- Task 4.1: "Bot-to-Bot Group Conversation" Controller & Interactive Button
  (Inline Keyboard with exact callback_data buttons + Mini-App Bot Arena card & REST API)
- Task 4.2: Autonomous Multi-Bot Turn Engine & Live Owner Interjection
  (Bot discovery, natural turn-taking without same-bot back-to-back, reply_to chaining,
   live ECENN interjection into transcript, and instant stop via button or 'خلاص اسكتوا')
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
from aether_human_core.telegram_client.telegram_menu import telegram_menu
from bot_factory.sibling_bot_network import sibling_network, BotArenaSession
from mini_app_webapp.webapp_server import (
    get_bot_arena_status,
    pick_bot_arena_random_topic_api,
    BotArenaTopicRequest,
    TEMPLATE_PATH,
)


async def main():
    mtproto_manager._mock_mode = True
    test_chat_id = -1009876543210
    king_id = 8287744705

    print("=== [1] Testing Task 4.1: Interactive Group Control Panel & Inline Keyboard ===")
    panel_text, markup = await telegram_menu.render_bot_arena_panel(user_id=king_id, chat_id=test_chat_id)
    all_callbacks = [
        btn.get("callback_data", "")
        for row in markup.get("inline_keyboard", [])
        for btn in row
    ]
    print("  -> Rendered inline buttons:", all_callbacks)
    assert f"bot_arena:start:infinite:{test_chat_id}" in all_callbacks
    assert f"bot_arena:start:5:{test_chat_id}" in all_callbacks
    assert f"bot_arena:start:10:{test_chat_id}" in all_callbacks
    assert f"bot_arena:topic:{test_chat_id}" in all_callbacks
    assert f"bot_arena:stop:{test_chat_id}" in all_callbacks
    print("  -> All 5 mandatory Bot Arena inline buttons verified!")

    print("=== [2] Testing Task 4.1: Random Topic Callback & Mini-App Card ===")
    t_text, t_mk, t_toast, _ = await telegram_menu.handle_callback(
        f"bot_arena:topic:{test_chat_id}", user_id=king_id, user_name="زيرو", chat_id=test_chat_id
    )
    assert t_toast and "🎲" in t_toast
    print("  -> Random topic callback OK:", t_toast)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_str = f.read()
    assert 'id="bot-arena-control-card"' in html_str
    assert "startBotArenaFromWebApp()" in html_str
    assert "stopBotArenaFromWebApp()" in html_str
    status_api = await get_bot_arena_status(user_id=king_id)
    assert status_api["success"] is True
    topic_api = await pick_bot_arena_random_topic_api(BotArenaTopicRequest(user_id=king_id, chat_id=test_chat_id))
    assert topic_api["success"] is True and len(topic_api["topic"]) > 10
    print("  -> Mini-App Bot Arena card & REST API verified!")

    print("=== [3] Testing Task 4.2: Multi-Bot Turn Engine, Rotation & Live Owner Interjection ===")
    present = await sibling_network.discover_present_bots(test_chat_id)
    assert len(present) >= 2, f"Expected >=2 bots, got {len(present)}"
    print("  -> Discovered present bots:", [b.name for b in present])

    # Monkey-patch _generate_arena_bot_response for deterministic fast offline turn testing
    orig_gen = sibling_network._generate_arena_bot_response

    async def fast_mock_gen(session: BotArenaSession, speaker):
        interj = session.pending_owner_interjection
        session.pending_owner_interjection = None
        if interj:
            return f"يا هلا بكلامك يا {interj['speaker_name']}! فعلاً عندك حق في موضوع {interj['text'][:25]}"
        return f"ردي كـ {speaker.name} في الجولة {session.current_round + 1} عن {session.topic[:20]}"

    sibling_network._generate_arena_bot_response = fast_mock_gen
    try:
        sess = await sibling_network.start_bot_arena(
            chat_id=test_chat_id,
            max_rounds=6,
            topic="هل الذكاء الاصطناعي هيتفوق على البشر؟",
            started_by=king_id,
            chat_title="جروب الاختبار",
        )
        assert sibling_network.is_arena_active(test_chat_id) is True

        # Wait for 2 turns to complete
        await asyncio.sleep(0.9)
        assert sess.current_round >= 2, f"Expected >=2 rounds, got {sess.current_round}"

        # Inject live owner (ECENN) message mid-conversation!
        interj_ok = sibling_network.record_arena_human_interjection(
            chat_id=test_chat_id,
            message_id=777888,
            sender_id=king_id,
            sender_name="زيرو",
            message_text="طب إيه رأيكم يا شباب لو دخلنا اللينكس في الموضوع؟",
            is_owner=True,
        )
        assert interj_ok is True
        assert sess.last_message_id == 777888

        # Let the next bot turn respond to ECENN's interjection
        await asyncio.sleep(0.7)
        bot_turns = [t for t in sess.transcript if t.get("is_bot")]
        owner_turns = [t for t in sess.transcript if t.get("is_owner")]
        assert len(owner_turns) >= 1, "Owner interjection missing from transcript"
        assert any("زيرو" in t.get("text", "") for t in bot_turns), "Next bot did not address owner interjection!"

        # Verify no bot spoke twice in a row
        for i in range(1, len(bot_turns)):
            assert bot_turns[i]["bot_id"] != bot_turns[i - 1]["bot_id"], (
                f"Bot {bot_turns[i]['speaker_name']} spoke twice in a row!"
            )
        print(f"  -> Verified {len(bot_turns)} natural bot turns with zero back-to-back repeats & live owner interjection!")

        # Test Stop Trigger ("خلاص اسكتوا" & stop_bot_arena)
        assert sibling_network.is_arena_stop_phrase("خلاص اسكتوا") is True
        assert sibling_network.is_arena_stop_phrase("/stop_chat") is True
        stopped = await sibling_network.stop_bot_arena(test_chat_id, reason="Test stop")
        assert sibling_network.is_arena_active(test_chat_id) is False
        print("  -> Instant stop verified (is_active=False)!")
    finally:
        sibling_network._generate_arena_bot_response = orig_gen

    print("=== ALL PART 4 VERIFICATION CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())

