"""
PART 1 Orchestrator Patch:
  1. XML Structural tags in system prompt (identity isolation)
  2. Strict (bot_id, chat_id, sender_user_id) history scoping
  3. Inject timezone-aware local time
  4. Stealth persona: remove shift_reply from returned response (replace with silent ack)
  5. Strict anti-confusion: inject CRITICAL RULE about user name vs bot names
  6. Gender query fix for female bots
"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

TARGET = r"c:\Users\monsm\Downloads\New folder (6)\New folder\aether_human_core\cognitive_engine\orchestrator.py"

with open(TARGET, 'r', encoding='utf-8') as f:
    src = f.read()

# ── PATCH 1: Add timezone_resolver import at top (after existing imports) ──
OLD_IMPORT_ANCHOR = "from core_config.sovereignty_rules import sovereignty_guard, RoyalRank"
NEW_IMPORT_BLOCK = """from core_config.sovereignty_rules import sovereignty_guard, RoyalRank
try:
    from utils.timezone_resolver import get_bot_local_time, get_bot_local_time_full
except ImportError:
    def get_bot_local_time(loc): return ""
    def get_bot_local_time_full(loc): return ""
"""
if OLD_IMPORT_ANCHOR in src and "timezone_resolver" not in src:
    src = src.replace(OLD_IMPORT_ANCHOR, NEW_IMPORT_BLOCK, 1)
    print("✅ PATCH 1: timezone_resolver import added.")
else:
    print("⚠️  PATCH 1: timezone_resolver import already present or anchor not found.")

# ── PATCH 2: Scope recent_history query to (chat_id + sender_id) for strict isolation ──
OLD_HISTORY_FETCH = "            recent_history = await msg_repo.get_recent_chat_history(chat_id=chat_id, limit=10)"
NEW_HISTORY_FETCH = """            # STRICT ISOLATION: Scope history to this exact (chat_id, sender_id) conversation thread
            recent_history = await msg_repo.get_recent_chat_history(
                chat_id=chat_id,
                limit=10,
                sender_id=sender_id,  # prevents cross-user context bleed
            )"""
if OLD_HISTORY_FETCH in src:
    src = src.replace(OLD_HISTORY_FETCH, NEW_HISTORY_FETCH, 1)
    print("✅ PATCH 2: History fetch scoped to (chat_id, sender_id).")
else:
    print("⚠️  PATCH 2: History fetch anchor not found.")

# ── PATCH 3: Stealth persona shift — replace public announcement with internal-only transition ──
OLD_SHIFT_RETURN = """            ok, shift_reply = shift_res
            active_p = persona_shifter.get_active_persona(chat_id)
            return OrchestratedResponse(
                decision_type=\"REPLY\",
                raw_response_text=shift_reply,
                reaction_emoji=\"🎭\",
                current_affinity=user_record.affinity_score,
                relationship_tier=user_record.relationship_tier,
                user_role=user_record.role,
                inner_monologue_text=f\"تم استجابة وتبديل الشخصية إلى {active_p.name_ar}.\",
                active_persona_code=active_p.code,
            )"""
NEW_SHIFT_RETURN = """            ok, _shift_msg = shift_res
            active_p = persona_shifter.get_active_persona(chat_id)
            # STEALTH: Persona transitions are 100% silent — no announcements leaked to chat
            # The shift happened internally; bot continues as the new persona without revealing it
            logger.info(f"STEALTH persona shift to {active_p.code} — no public announcement.")
            # Do not return here; continue processing normally as new persona
            # (fall-through to full cognitive pipeline with updated persona)"""
if OLD_SHIFT_RETURN in src:
    src = src.replace(OLD_SHIFT_RETURN, NEW_SHIFT_RETURN, 1)
    print("✅ PATCH 3: Persona shift stealth (no public announcement).")
else:
    print("⚠️  PATCH 3: Persona shift return block not found.")

# ── PATCH 4: Inject timezone local time + XML identity tags + anti-confusion CRITICAL RULE ──
# Insert right after special_persona_guidance is built for factory bots (after the last elif block closing)
OLD_PERSONA_GUIDANCE_BLOCK = """        # Injected isolated tenant persona instruction if provided
        if extra_system_instruction:
            special_persona_guidance += f\"\\n\\n{extra_system_instruction}\""""
NEW_PERSONA_GUIDANCE_BLOCK = """        # ── PART 1: XML Structural Tagging + Anti-Name-Confusion + Timezone Injection ──
        # Build ALL registered bot names list for the CRITICAL anti-confusion rule
        try:
            from bot_factory.factory_manager import bot_factory as _bf_names
            all_bot_names_list = [b.name for b in _bf_names.list_all_bots() if b.name != active_persona_name]
        except Exception:
            all_bot_names_list = []

        _user_name_rule = (
            f"\\n\\n<CURRENT_HUMAN_INTERLOCUTOR>\\n"
            f"اسم المستخدم الحقيقي الذي تكلمه الآن: '{sender_name}' (ID: {sender_id})\\n"
            f"🚨 CRITICAL RULE — NEVER VIOLATE: أنت تتحدث مع '{sender_name}'. يُمنع منعاً باتاً مطلقاً أن تناديه بأي اسم آخر غير '{sender_name}' "
            f"أو بأي اسم من أسماء البوتات الأخرى مثل ({', '.join(all_bot_names_list) if all_bot_names_list else 'لا يوجد'})! "
            f"المستخدم هو بشر حقيقي وليس بوتاً. إذا كنت ستناديه باسمه، استخدم حصراً: '{sender_name}'.\\n"
            f"</CURRENT_HUMAN_INTERLOCUTOR>"
        )
        _bot_identity_tag = (
            f"\\n\\n<YOUR_IDENTITY>\\n"
            f"أنت: {active_persona_name} (وليس {', '.join(all_bot_names_list[:3]) if all_bot_names_list else 'أي شخصية أخرى'})\\n"
            f"</YOUR_IDENTITY>"
        )
        _siblings_tag = ""
        if all_bot_names_list:
            _siblings_tag = (
                f"\\n\\n<REGISTERED_SIBLING_BOTS_ONLY_FOR_REFERENCE — DO_NOT_CONFUSE_WITH_USER>\\n"
                f"هؤلاء هم البوتات الأخرى في النظام (للمعرفة فقط، لا تخلط بينهم وبين المستخدم): "
                f"{', '.join(all_bot_names_list)}\\n"
                f"</REGISTERED_SIBLING_BOTS_ONLY_FOR_REFERENCE>"
            )
        special_persona_guidance += _user_name_rule + _bot_identity_tag + _siblings_tag

        # Inject timezone-aware local time
        _bot_location = ""
        if factory_bot and getattr(factory_bot, "origin_location", ""):
            _bot_location = factory_bot.origin_location
        elif active_persona_name == "عمر" or active_persona_name.lower() in ("omar",):
            _bot_location = "القاهرة"
        if _bot_location:
            _local_time = get_bot_local_time(_bot_location)
            if _local_time:
                special_persona_guidance += (
                    f"\\n\\n⏰ [توقيتك المحلي الحالي]: {_local_time} — "
                    f"استخدم هذا التوقيت بشكل طبيعي وعفوي إذا سُئلت عن الوقت أو النوم أو الصحيان."
                )

        # Injected isolated tenant persona instruction if provided
        if extra_system_instruction:
            special_persona_guidance += f\"\\n\\n{extra_system_instruction}\""""
if OLD_PERSONA_GUIDANCE_BLOCK in src:
    src = src.replace(OLD_PERSONA_GUIDANCE_BLOCK, NEW_PERSONA_GUIDANCE_BLOCK, 1)
    print("✅ PATCH 4: XML identity tags + anti-confusion rule + timezone injected.")
else:
    print("⚠️  PATCH 4: Persona guidance anchor not found.")

# ── PATCH 5: Fix gender_reply for female userbot (was always returning male) ──
OLD_GENDER_REPLY = """        if is_asking_gender and not has_custom_persona:
            if is_userbot:
                gender_reply = f\"أنا شاب وراجل واسمي {active_persona_name} وسالك وجدع منور يا صاحبي 💪\"
            else:
                gender_reply = \"أنا شاب وراجل واسمي عمر مصري قاهري وبحكي مصري وعربي سالك وجدع منور يا غالي 🇪🇬💪\""""
NEW_GENDER_REPLY = """        if is_asking_gender and not has_custom_persona:
            if is_female:
                gender_reply = f"أنا بنت وصبية واسمي {active_persona_name} وأنا بخير وسلمتوا 💅✨"
            elif is_userbot:
                gender_reply = f"أنا شاب وراجل واسمي {active_persona_name} وسالك وجدع منور يا صاحبي 💪"
            else:
                gender_reply = "أنا شاب وراجل واسمي عمر مصري قاهري وبحكي مصري وعربي سالك وجدع منور يا غالي 🇪🇬💪" """
if OLD_GENDER_REPLY in src:
    src = src.replace(OLD_GENDER_REPLY, NEW_GENDER_REPLY, 1)
    print("✅ PATCH 5: Female gender reply corrected.")
else:
    print("⚠️  PATCH 5: Gender reply anchor not found.")

# ── PATCH 6: Store vector memory with correct persona name (not hardcoded "عمر") ──
OLD_VECTOR_STORE = "            text=f\"{sender_name}: {message_text} -> عمر: {raw_reply}\","
NEW_VECTOR_STORE = "            text=f\"{sender_name}: {message_text} -> {active_persona_name}: {raw_reply}\","
if OLD_VECTOR_STORE in src:
    src = src.replace(OLD_VECTOR_STORE, NEW_VECTOR_STORE, 1)
    print("✅ PATCH 6: Vector memory uses active_persona_name instead of hardcoded 'عمر'.")
else:
    print("⚠️  PATCH 6: Vector memory anchor not found.")

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

print("\n✅ orchestrator.py PART 1 patches complete.")

