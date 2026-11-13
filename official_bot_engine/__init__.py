"""
Official Bot Engine Package for Project Aether-Human (V2.0).
Coordinates Version A (Official BotFather Bot + WebApp) and shared game/chat intelligence.
"""

from official_bot_engine.game_chat_bridge import (
    game_chat_bridge,
    GameChatBridge,
    GameOutcomeResult,
)
from official_bot_engine.academic_research_assistant.research_lab import (
    research_assistant,
    AcademicResearchAssistant,
)

__all__ = [
    "game_chat_bridge",
    "GameChatBridge",
    "GameOutcomeResult",
    "research_assistant",
    "AcademicResearchAssistant",
]

