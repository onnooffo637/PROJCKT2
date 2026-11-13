"""Offline verification for PART 1 (no network, no DB)."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.timezone_resolver import resolve_timezone, get_bot_local_time
for loc in ["العراق", "بغداد", "Syria", "السعودية", "المغرب", "دبي", "القاهرة", "مكان غريب"]:
    print(f"{loc:12} -> {resolve_timezone(loc)[0]:20} | {get_bot_local_time(loc)}")

from aether_human_core.database.postgres.repositories.message_repo import MessageRepository
a = MessageRepository.build_thread_scope("master_omar_official", 111)
b = MessageRepository.build_thread_scope("bot_maryam", 111)
print("thread scopes differ per bot:", a != b, "| len", len(a))

from bot_factory.sibling_bot_network import sibling_network, GroupLedgerEntry
from bot_factory.group_arbiter import group_arbiter
bots = group_arbiter.get_all_active_bots()
print("bots:", {k: (v.name, v.numeric_id) for k, v in bots.items()})

chat = -100999
for bid in bots:
    group_arbiter.record_presence(chat, bid)

cases = [
    ("يا عمري انت جميل اوي", None, "General flirt (old false positive)"),
    ("الفيلم ده غبي وتافه", None, "General insult"),
    ("عبد الرحمن قال الفيلم تافه", None, "Creator name + distant word"),
    ("مريم انتي غبية", None, "Explicit sibling mention"),
    ("انتي غبية", 9150129512, "Reply to Maryam's message"),
    ("gg ez", None, "gaming slang gg"),
    ("زيرو ده غبي", None, "Direct creator insult"),
    ("يا حمار يا زيرو", None, "Direct creator insult (before)"),
]
from bot_factory.factory_manager import bot_factory
cur = bot_factory.get_bot("master_omar_official") or list(bot_factory.list_all_bots())[0]
for i, (txt, rt, label) in enumerate(cases):
    sibling_network._last_defense_time.clear()
    e = sibling_network.record_group_message(5000 + i, chat, "t", 42, "Ali", txt, reply_to_from_id=rt)
    res = sibling_network.evaluate_sibling_defense(e, cur)
    print(f"[{label}] target={e.target_bot_name} flirt={e.is_flirt} dis={e.is_disrespect} -> DEFEND={bool(res)}"
          + (f" by {res[1].name}: {res[0]}" if res else ""))

# dedup: same message twice -> same entry, second evaluation no defense
e1 = sibling_network.record_group_message(7777, chat, "t", 42, "Ali", "مريم غبية")
r1 = sibling_network.evaluate_sibling_defense(e1, cur)
e2 = sibling_network.record_group_message(7777, chat, "t", 42, "Ali", "مريم غبية")
print("dedup same entry:", e1 is e2, "| second defense:", sibling_network.evaluate_sibling_defense(e2, cur))

from aether_human_core.cognitive_engine.persona_shifter import persona_shifter
print("normal user 'خليك جدع' shift:", persona_shifter.evaluate_natural_language_shift(42, "خليك جدع معايا", None))
