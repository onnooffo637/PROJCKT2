"""Offline verification for PART 2 (Tasks 2.1, 2.2, 2.3)."""
import sys, os, asyncio, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
from aether_human_core.telegram_client.human_typer import human_typer
from aether_human_core.config.llm_router import sanitize_and_validate_reply
from aether_human_core.psychology_engine.anti_toxicity import anti_toxicity
from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
from live_voip_call_engine.call_signaling_interceptor import call_signaling_interceptor

# 1. Task 2.1 verification
d_idle, act_idle = mtproto_manager.compute_userbot_phase1_unseen_delay(chat_id=123456, sender_id=999999)
mtproto_manager._userbot_last_conv_ts[123456] = time.time() - 30.0  # 30s ago (< 2 mins)
d_act, act_flag = mtproto_manager.compute_userbot_phase1_unseen_delay(chat_id=123456, sender_id=999999)
print(f"Phase 1 Idle delay (expect 15-90s): {d_idle:.1f}s (active={act_idle})")
print(f"Phase 1 Active delay (expect 2-8s): {d_act:.1f}s (active={act_flag})")
assert 15.0 <= d_idle <= 90.0 and not act_idle
assert 2.0 <= d_act <= 8.0 and act_flag

t_short = mtproto_manager.compute_userbot_phase2_think_delay("ازيك يسطا", sender_id=999999)
t_long = mtproto_manager.compute_userbot_phase2_think_delay(" ".join(["كلمة"] * 25), sender_id=999999)
print(f"Phase 2 Think short (15-75s): {t_short:.1f}s | long: {t_long:.1f}s")
assert 15.0 <= t_short <= 75.0 and 15.0 <= t_long <= 75.0

sample_reply = "والله لسه صاحي وبشرب قهوة انت بتعمل ايه دلوقتي"  # 45 chars
t_type = human_typer.calculate_typing_delay(sample_reply, is_userbot=True)
print(f"Phase 3 Typing for {len(sample_reply)} chars (~3.5-5 cps -> 9-13s): {t_type:.1f}s")
assert 8.0 <= t_type <= 15.0

for msg in ["تمام", "ماشي", "اوك", "عامل ايه في اللينكس؟"]:
    skip, emo = mtproto_manager.evaluate_selective_reply_filter(msg, "text", 999999, True)
    print(f"Selective Filter '{msg}' -> skip={skip}, reaction={emo}")

# 2. Task 2.2 verification
dirty = "من عيوني يا غالي تحت أمرك يا باشا هقولك الحل دلوقتي أقدر أساعدك بإيه"
cleaned = sanitize_and_validate_reply(dirty)
print(f"Sycophancy scrubber: '{dirty}' -> '{cleaned}'")
assert "من عيوني" not in cleaned and "تحت أمرك" not in cleaned and "أقدر أساعدك" not in cleaned
print("Anti-toxicity retort:", anti_toxicity.get_dignified_response_to_insult("egyptian"))

# 3. Task 2.3 verification
async def test_voip():
    res_king = await call_signaling_interceptor.evaluate_selective_voip_decision(8287744705, "ECENN")
    print("VoIP Creator decision:", res_king)
    assert res_king["should_answer"] is True

    # Simulate annoyed/high cortisol mood for a regular caller
    h = endocrine_engine.get_current_state()
    old_c = h.cortisol
    h.cortisol = 0.80
    res_annoyed = await call_signaling_interceptor.evaluate_selective_voip_decision(555666777, "Stranger")
    print("VoIP Annoyed mood stranger decision:", res_annoyed)
    assert res_annoyed["should_answer"] is False
    h.cortisol = old_c

    # Simulate spamming caller (2nd call within 10 mins)
    res_spam = await call_signaling_interceptor.evaluate_selective_voip_decision(555666777, "Stranger")
    print("VoIP Spam call decision:", res_spam)
    assert res_spam["should_answer"] is False and res_spam.get("is_spam") is True

asyncio.run(test_voip())
print("\nALL PART 2 VERIFICATIONS PASSED!")

