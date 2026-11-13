"""
Bot Factory Package for Project Aether-Human (V2.0).
Provides multi-tenant official bots and MTProto userbots creation,
gender switching (ولد / بنت), and pre-built character persona templates.
"""

from bot_factory.models import (
    BotPlatformType,
    BotGender,
    BotInstanceConfig,
)
from bot_factory.persona_templates import (
    template_registry,
    FactoryPersonaTemplate,
    FactoryTemplateRegistry,
)
from bot_factory.factory_manager import (
    bot_factory,
    MultiBotFactoryService,
)

__all__ = [
    "BotPlatformType",
    "BotGender",
    "BotInstanceConfig",
    "template_registry",
    "FactoryPersonaTemplate",
    "FactoryTemplateRegistry",
    "bot_factory",
    "MultiBotFactoryService",
]

