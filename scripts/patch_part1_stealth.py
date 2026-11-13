"""
PART 1 — Task 1.4 Stealth persona + NameError fix in cognitive cache path.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\monsm\Downloads\New folder (6)\New folder"
ORCH = ROOT + r"\aether_human_core\cognitive_engine\orchestrator.py"
PS = ROOT + r"\aether_human_core\cognitive_engine\persona_shifter.py"


def rw(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def ww(p, s):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sub(src, old, new, label):
    nl = "\r\n" if "\r\n" in src else "\n"
    o = old.replace("\r\n", "\n").replace("\n", nl)
    n = new.replace("\r\n", "\n").replace("\n", nl)
    if o in src:
        print(f"✅ {label}")
        return src.replace(o, n, 1)
    print(f"⚠️  {label} — anchor NOT found")
    return src


# ───────── orchestrator ─────────
o = rw(ORCH)
o = sub(o,
"""            logger.info(f"STEALTH persona shift to {active_p.code} — no public announcement.")
            # Do not return here; continue processing normally as new persona
            # (fall-through to full cognitive pipeline with updated persona)
""",
"""            logger.info(f"STEALTH persona shift to {active_p.code} — no public announcement.")
            # Explicit slash commands (/persona ...) get only a silent reaction — never a text leak.
            if message_text.strip().startswith("/"):
                return OrchestratedResponse(
                    decision_type="REACT_ONLY",
                    reaction_emoji="👌",
                    current_affinity=user_record.affinity_score,
                    relationship_tier=user_record.relationship_tier,
                    user_role=user_record.role,
                    inner_monologue_text=f"تحول داخلي صامت إلى {active_p.code}.",
                    active_persona_code=active_p.code,
                )
            # Natural-language shift: fall through and simply answer AS the new persona.
""",
"orchestrator: slash persona command -> silent reaction")

# NameError: is_scholar_mode referenced in cache block before assignment
o = sub(o,
"""        has_custom_persona = (tenant_persona is not None and getattr(tenant_persona, "persona_name", "عمر") != "عمر")
        if not active_rules and not has_custom_persona:""",
"""        has_custom_persona = (tenant_persona is not None and getattr(tenant_persona, "persona_name", "عمر") != "عمر")
        is_scholar_mode = False  # finalised later; defined here so the cache path never raises NameError
        is_factory_persona = bool(target_bot_id and target_bot_id != "master_omar_official") or is_userbot
        if not active_rules and not has_custom_persona and not is_factory_persona:""",
"orchestrator: cache NameError fix + cache disabled for non-Omar personas")
ww(ORCH, o)

# ───────── persona_shifter ─────────
p = rw(PS)

# set_persona: internal-only message (callers such as the admin menu may still show it privately)
p = sub(p,
"""        if chat_id is not None:
            self._chat_states[chat_id] = new_state
            scope_desc = f"لهذه المحادثة ({chat_id})"
        else:
            self._global_state = new_state
            scope_desc = "عاماً للنظام ككل\"""",
"""        if chat_id is not None:
            self._chat_states[chat_id] = new_state
            scope_desc = f"لهذه المحادثة ({chat_id})"
        else:
            self._global_state = new_state
            scope_desc = "عاماً للنظام ككل"
        # STEALTH (Task 1.4): this text is an admin-panel receipt ONLY. The cognitive pipeline never
        # forwards it into a DM or group — chat transitions are 100% silent internal state changes.""",
"persona_shifter: stealth note in set_persona")

# Natural language + slash shifts: King / admins only, tightened triggers (no more 'خليك جدع' -> persona change)
p = sub(p,
"""        is_king = SovereigntyProtocolService.is_the_king(sender_id)
        clean = message_text.strip().lower()

        # Check slash commands first""",
"""        is_king = SovereigntyProtocolService.is_the_king(sender_id)
        clean = message_text.strip().lower()
        try:
            from core_config.sovereignty_rules import sovereignty_guard as _sg
            is_privileged = is_king or _sg.is_other_admin(sender_id)
        except Exception:
            is_privileged = is_king
        if not is_privileged:
            # Ordinary users can NEVER flip the persona (prevented random shifts from casual phrases).
            return None

        # Check slash commands first""",
"persona_shifter: only King/admins may shift")

p = sub(p,
"""        shift_triggers = [
            "تحول", "اتحول", "خليك", "كن", "ادخل وضع", "فعل شخصية", "العب دور",
            "ارجع طبيعي", "ارجع لوضعك", "شخصية", "وضع"
        ]

        if any(trig in clean for trig in shift_triggers):
            for kw, code in self._persona_keywords.items():
                if kw in clean:""",
"""        shift_triggers = [
            "اتحول لوضع", "اتحول ل", "ادخل وضع", "فعل شخصية", "فعّل شخصية", "العب دور",
            "ارجع طبيعي", "ارجع لوضعك", "غير شخصيتك", "شغل وضع",
        ]

        if any(trig in clean for trig in shift_triggers):
            # longest keyword first so 'قاهر الاشرار' wins over 'شرير'
            for kw, code in sorted(self._persona_keywords.items(), key=lambda kv: -len(kv[0])):
                if re.search(rf"(?<!\\w){re.escape(kw)}(?!\\w)", clean):""",
"persona_shifter: tightened natural-language triggers")

p = sub(p,
"""            logger.info(f"Autonomous subconscious drift transitioned Omar to persona: {selected_code}")""",
"""            logger.info(f"Autonomous subconscious drift (silent) -> persona: {selected_code}")""",
"persona_shifter: drift log")
ww(PS, p)
print("Done.")

