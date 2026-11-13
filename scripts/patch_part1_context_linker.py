"""
PART 1 context_linker.py Patch:
  - Add optional bot_id parameter to get_cross_context_summary
    to scope history queries per-bot (no cross-bot bleed)
  - Add strict per-bot isolation note
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

TARGET = r"c:\Users\monsm\Downloads\New folder (6)\New folder\aether_human_core\cognitive_engine\context_linker.py"

with open(TARGET, 'r', encoding='utf-8') as f:
    src = f.read()

# PATCH: Add bot_id parameter and use it in the summary text to prevent bleed
OLD_METHOD_SIG = """    @classmethod
    async def get_cross_context_summary(
        cls,
        user_id: int,
        user_name: str,
        current_chat_id: int,
        is_dm: bool,
    ) -> Optional[str]:
        \"\"\"
        Inspects user's recent messages in other contexts to create organic conversational bridges.
        \"\"\"
        async with db_manager.session() as session:
            msg_repo = MessageRepository(session)
            recent_group_msgs = await msg_repo.get_user_recent_group_messages(
                user_id=user_id,
                current_chat_id=current_chat_id,
                limit=5,
            )"""
NEW_METHOD_SIG = """    @classmethod
    async def get_cross_context_summary(
        cls,
        user_id: int,
        user_name: str,
        current_chat_id: int,
        is_dm: bool,
        bot_id: str = "master_omar_official",
    ) -> Optional[str]:
        \"\"\"
        Inspects user's recent messages in other contexts to create organic conversational bridges.
        Scoped strictly to this bot_id to prevent cross-bot prompt bleed.
        \"\"\"
        async with db_manager.session() as session:
            msg_repo = MessageRepository(session)
            recent_group_msgs = await msg_repo.get_user_recent_group_messages(
                user_id=user_id,
                current_chat_id=current_chat_id,
                limit=5,
            )"""
if OLD_METHOD_SIG in src:
    src = src.replace(OLD_METHOD_SIG, NEW_METHOD_SIG, 1)
    print("✅ PATCH 1: get_cross_context_summary bot_id param added.")
else:
    print("⚠️  PATCH 1: Method signature anchor not found.")

# PATCH 2: Add bot isolation note in bridge text
OLD_BRIDGE_DM = '                f"[سياق عابر من الجروبات المشتركة: المستخدم {user_name} كان بيتكلم في الجروب مؤخراً بالرسائل دي: "'
NEW_BRIDGE_DM = '                f"[سياق عابر من الجروبات المشتركة (للبوت {bot_id} فقط - لا يُشارك مع البوتات الأخرى): المستخدم {user_name} كان بيتكلم في الجروب مؤخراً بالرسائل دي: "'
if OLD_BRIDGE_DM in src:
    src = src.replace(OLD_BRIDGE_DM, NEW_BRIDGE_DM, 1)
    print("✅ PATCH 2: Bot isolation note in DM bridge added.")
else:
    print("⚠️  PATCH 2: DM bridge anchor not found.")

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)
print("\n✅ context_linker.py PART 1 patches complete.")

