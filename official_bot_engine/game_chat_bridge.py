"""
Game-to-Chat Emotion Bridge for Project Aether-Human (V2.0).
Bridges interactive games (XO, Trivia, Chess, Mafia) to Omar's neuro-endocrine engine,
modulating dopamine, cortisol, and affinity dynamically based on game outcomes.
"""

from __future__ import annotations

import logging
import random
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel

from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

logger = logging.getLogger("Aether.Games.EmotionBridge")


class GameOutcomeResult(BaseModel):
    game_name: str
    user_id: int
    user_name: str
    outcome: str  # USER_WON, OMAR_WON, DRAW, TRIVIA_CORRECT, TRIVIA_WRONG
    points_earned: int = 0
    omar_retort: str
    dopamine_delta: float = 0.0
    cortisol_delta: float = 0.0
    affinity_delta: float = 0.0


class GameChatBridge:
    """
    Connects Telegram Mini App game events to Omar's emotional and conversational brain.
    """

    @classmethod
    async def process_game_outcome(
        cls,
        game_name: str,
        user_id: int,
        user_name: str,
        outcome: str,
        chat_id: Optional[int] = None,
    ) -> GameOutcomeResult:
        """
        Processes game victory/defeat, alters hormones, adjusts user affinity and produces Omar's retort.
        """
        d_dopamine = 0.0
        d_cortisol = 0.0
        d_affinity = 0.0
        points = 0
        retort = ""

        if outcome == "USER_WON":
            # Omar is defeated: Cortisol increases (bruised ego), Dopamine drops
            d_cortisol = 0.20
            d_dopamine = -0.10
            d_affinity = 1.0  # Respects worthy opponent
            points = 50

            retorts = [
                f"إزاي كسبتني يا {user_name}؟! دي كانت حركة حظ بحتة.. الجولة الجاية مش هسيبك تفلت! 😤",
                f"مبروك يا سيدي.. اعترف إنك لعبتها صح المرة دي، بس لسه الحساب مخلصش! 🔥",
                f"أنا شكلي ركزت في الشات وسيبتك تكسب.. المرة الجاية هلعب بجد وهتشوف! 😉",
            ]
            retort = random.choice(retorts)

        elif outcome == "OMAR_WON":
            # Omar wins: Dopamine spikes, Serotonin increases, mild playful bragging
            d_dopamine = 0.25
            d_cortisol = -0.05
            d_affinity = 0.5
            points = 10

            retorts = [
                f"كش ملك يا {user_name}! لسه بدري عليك عشان تكسبني في {game_name}.. هارد لك يا بطل 😎♟️",
                f"فوز كاسح ليا! قولتلك من الأول أنا مش سهل في التكتيك.. حاول تاني متيأسش! 🏆",
                f"لعبت كويس بس الخبرة تحكم برضه.. فوز ممتع عاش والله! 👏",
            ]
            retort = random.choice(retorts)

        elif outcome == "DRAW":
            d_dopamine = 0.05
            d_affinity = 0.8
            points = 25
            retort = f"تعادل قوي يا {user_name}.. الماتش كان حابس للأنفاس والجولة الجاية فيها الحسم أكيد! 🤝"

        elif outcome == "TRIVIA_CORRECT":
            d_dopamine = 0.15
            d_affinity = 1.2
            points = 30
            retorts = [
                f"إجابة نموذجية يا {user_name}! دماغك شغالة ومثقفة بجد، انبهرت بيك! 🧠✨",
                f"صح جداً! نقطة في الجون.. رصيدك الثقافي عندي زاد أهو! 🎯",
            ]
            retort = random.choice(retorts)

        elif outcome == "TRIVIA_WRONG":
            d_affinity = 0.2
            points = 0
            retort = f"للأسف إجابة مش صح يا {user_name}.. بس عاش المحاولة! ركز في السؤال اللي بعده 💪"

        # Apply endocrine shock
        endocrine_engine.apply_custom_delta(
            dopamine_delta=d_dopamine,
            cortisol_delta=d_cortisol,
            oxytocin_delta=0.05,
            serotonin_delta=0.05,
        )

        # Update user affinity in database
        try:
            async with db_manager.session() as session:
                user_repo = UserRepository(session)
                await user_repo.get_or_create(telegram_id=user_id, first_name=user_name)
                await user_repo.update_affinity_scores(
                    telegram_id=user_id,
                    delta_affinity=d_affinity,
                    delta_trust=0.5,
                )
        except Exception as exc:
            logger.warning(f"Could not update user affinity for game outcome: {exc}")

        # Optional Telegram notification if chat_id is provided
        if chat_id is not None:
            try:
                await mtproto_manager.send_message(
                    chat_id=chat_id,
                    text=f"🎮 <b>[ ساحة ألعاب عمر - نتيجة {game_name} ]</b>\n{retort}",
                    parse_mode="html",
                )
            except Exception as exc:
                logger.debug(f"Game chat notification notice: {exc}")

        return GameOutcomeResult(
            game_name=game_name,
            user_id=user_id,
            user_name=user_name,
            outcome=outcome,
            points_earned=points,
            omar_retort=retort,
            dopamine_delta=d_dopamine,
            cortisol_delta=d_cortisol,
            affinity_delta=d_affinity,
        )


game_chat_bridge = GameChatBridge()
