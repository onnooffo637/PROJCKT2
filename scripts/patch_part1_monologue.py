import sys
sys.stdout.reconfigure(encoding='utf-8')
P = r"c:\Users\monsm\Downloads\New folder (6)\New folder\aether_human_core\cognitive_engine\inner_monologue.py"
with open(P, 'r', encoding='utf-8', newline='') as f:
    s = f.read()

OLD = """        try:
            res_json = await llm_pool.generate_json("""
NEW = """        # ── PART 1 Isolation Envelope: identity / interlocutor XML tags (zero name confusion, zero persona bleed)
        system_instruction = (
            f"<YOUR_IDENTITY>{persona_name or 'عمر'} ({'أنثى' if persona_gender == 'female' else 'ذكر'})</YOUR_IDENTITY>\\n"
            f"<CURRENT_HUMAN_INTERLOCUTOR>{user_display_name} (ID: {user_vector.user_id})</CURRENT_HUMAN_INTERLOCUTOR>\\n"
            f"CRITICAL RULE: You are talking to \\"{user_display_name}\\". NEVER call this user by any bot name "
            f"and never mix this conversation with any other user or any other bot's conversation. "
            f"Never announce a change of mood, mode or persona — just behave naturally.\\n\\n"
            + system_instruction
        )

        try:
            res_json = await llm_pool.generate_json("""
nl = "\r\n" if "\r\n" in s else "\n"
OLD = OLD.replace("\n", nl); NEW = NEW.replace("\n", nl)
if OLD in s and "<YOUR_IDENTITY>" not in s:
    s = s.replace(OLD, NEW, 1)
    print("✅ inner_monologue isolation envelope added")
else:
    print("⚠️ anchor missing or already patched")
with open(P, 'w', encoding='utf-8', newline='') as f:
    f.write(s)

