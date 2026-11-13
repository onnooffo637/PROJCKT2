"""
Interactive Group & Direct Games Engine for Project Aether-Human (V2.0 - V4.0).
Provides rich in-chat games:
1. Tic-Tac-Toe (XO) against Omar with dynamic board editing
2. Mega Trivia Quiz Bank with 4 interactive multiple choices
3. Rock-Paper-Scissors (RPS) with instant emotional reaction
4. Number Guess arena
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Dict, Any, List, Optional, Tuple

from official_bot_engine.game_chat_bridge import game_chat_bridge
from mini_app_webapp.games_engine import TriviaBank

logger = logging.getLogger("Aether.Telegram.GroupGames")


class GroupXOGame:
    """
    Manages an active Tic-Tac-Toe session directly rendered in Telegram chat messages.
    """

    def __init__(self, chat_id: int, player_id: int, player_name: str):
        self.chat_id = chat_id
        self.player_id = player_id
        self.player_name = player_name
        self.board = [" "] * 9
        self.is_over = False
        self.winner: Optional[str] = None
        self.turn = "X"  # Player is X, Omar is O
        self.created_at = time.time()

    def make_move(self, index: int, symbol: str) -> bool:
        if 0 <= index < 9 and self.board[index] == " " and not self.is_over:
            self.board[index] = symbol
            self._check_winner()
            return True
        return False

    def omar_ai_move(self) -> Optional[int]:
        """
        Smart Omar AI choosing winning move, block, or optimal square.
        """
        if self.is_over:
            return None

        # 1. Try to win
        for i in range(9):
            if self.board[i] == " ":
                self.board[i] = "O"
                if self._check_win_condition("O"):
                    self.board[i] = " "
                    return i
                self.board[i] = " "

        # 2. Block player win
        for i in range(9):
            if self.board[i] == " ":
                self.board[i] = "X"
                if self._check_win_condition("X"):
                    self.board[i] = " "
                    return i
                self.board[i] = " "

        # 3. Take center
        if self.board[4] == " ":
            return 4

        # 4. Take corners or random empty
        empty = [i for i, v in enumerate(self.board) if v == " "]
        if empty:
            corners = [c for c in [0, 2, 6, 8] if c in empty]
            return random.choice(corners) if corners else random.choice(empty)
        return None

    def _check_win_condition(self, s: str) -> bool:
        combos = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6),
        ]
        return any(self.board[a] == self.board[b] == self.board[c] == s for a, b, c in combos)

    def _check_winner(self) -> None:
        if self._check_win_condition("X"):
            self.is_over = True
            self.winner = "X"
        elif self._check_win_condition("O"):
            self.is_over = True
            self.winner = "O"
        elif " " not in self.board:
            self.is_over = True
            self.winner = "DRAW"

    def render_keyboard(self, game_id: str) -> Dict[str, Any]:
        symbol_map = {" ": "⬜", "X": "❌", "O": "⭕"}
        rows = []
        for r in range(3):
            row = []
            for c in range(3):
                idx = r * 3 + c
                val = self.board[idx]
                text = symbol_map.get(val, "⬜")
                cb = f"xo:{game_id}:{idx}" if val == " " and not self.is_over else f"xo_noop:{idx}"
                row.append({"text": text, "callback_data": cb})
            rows.append(row)

        if self.is_over:
            rows.append([{"text": "🔄 جولة جديدة ⚡", "callback_data": f"act:game_xo"}])
        else:
            rows.append([{"text": "🏳️ استسلام (انسحاب)", "callback_data": f"xo:{game_id}:surrender"}])

        return {"inline_keyboard": rows}


class GroupGamesEngine:
    """
    Coordinates multi-player and bot games directly inside Telegram chats.
    """

    def __init__(self):
        self.active_xo_games: Dict[str, GroupXOGame] = {}
        self.active_trivia_questions: Dict[str, Dict[str, Any]] = {}

    def render_games_lobby(self, user_name: str) -> Tuple[str, Dict[str, Any]]:
        text = (
            f"🎮 <b>ساحة ألعاب وتحديات عُـمـر التفاعلية</b> 🏆\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"مرحباً بك يا <b>{user_name}</b>! اختر لعبتك المفضلة للتحدي المباشر في الشات:\n\n"
            f"• ❌⭕ <b>إكس أو (Tic-Tac-Toe):</b> تحدى ذكاء عمر التكتيكي مباشرة!\n"
            f"• 🧠 <b>بنك الأسئلة والتحديات (Trivia):</b> مسابقة معلومات عامة وخيارات فورية.\n"
            f"• ✊✋✌️ <b>حجرة ورقة مقص (RPS):</b> حظ وسرعة بديهة ضد عمر.\n"
            f"• 🔢 <b>خمن الرقم السري (Guess):</b> عمر هيخبي رقم وانت تحاول تكتشفه.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>اضغط على الزر لبدء الجولة فوراً:</i>"
        )
        buttons = [
            [{"text": "❌⭕ بدء لعبة إكس أو (XO)", "callback_data": "act:game_xo", "style": "success"}],
            [{"text": "🧠 سؤال ثقافي سريع (Trivia)", "callback_data": "act:game_trivia", "style": "primary"}],
            [{"text": "✊✋✌️ حجرة ورقة مقص (RPS)", "callback_data": "act:game_rps", "style": "primary"}],
            [{"text": "🚀 فتح ساحة الألعاب الكاملة (Mini App) 🎮", "callback_data": "menu:webapp", "style": "success"}],
            [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
        ]
        return text, {"inline_keyboard": buttons}

    def start_xo_game(self, chat_id: int, user_id: int, user_name: str) -> Tuple[str, Dict[str, Any]]:
        game_id = f"{chat_id}_{user_id}_{int(time.time())}"
        game = GroupXOGame(chat_id, user_id, user_name)
        self.active_xo_games[game_id] = game

        text = (
            f"❌⭕ <b>لعبة إكس أو ضد عمر</b> 🎮\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>اللاعب:</b> {user_name} (❌)\n"
            f"🤖 <b>المنافس:</b> عمر (⭕)\n"
            f"دورك الآن يا {user_name}، اختر خانة فارغة من اللوحة أدناه:"
        )
        return text, game.render_keyboard(game_id)

    async def handle_xo_click(
        self, game_id: str, cell_idx_str: str, clicker_id: int, clicker_name: str
    ) -> Tuple[str, Dict[str, Any], Optional[str]]:
        game = self.active_xo_games.get(game_id)
        if not game:
            return "⚠️ انتهت صلاحية هذه الجولة أو غير موجودة.", {"inline_keyboard": [[{"text": "🔄 بدء جولة جديدة", "callback_data": "act:game_xo"}]]}, None

        if cell_idx_str == "surrender":
            game.is_over = True
            game.winner = "O"
            outcome_res = await game_chat_bridge.process_game_outcome(
                game_name="XO", user_id=game.player_id, user_name=game.player_name, outcome="OMAR_WON", chat_id=game.chat_id
            )
            text = (
                f"🏳️ <b>انسحب اللاعب {game.player_name}!</b>\n"
                f"فوز كاسح لـ «عمر» ⭕🏆\n\n"
                f"💬 <b>عمر:</b> <i>{outcome_res.omar_retort}</i>"
            )
            return text, game.render_keyboard(game_id), "انسحبت يا بطل! 😅"

        if clicker_id != game.player_id:
            return None, None, "⚠️ هذه الجولة مخصصة لمن بدأها فقط! اضغط بدء جولة جديدة لتلعب دورك."

        try:
            cell_idx = int(cell_idx_str)
        except ValueError:
            return None, None, None

        if not game.make_move(cell_idx, "X"):
            return None, None, "⚠️ الخانة مشغولة بالفعل!"

        # Check if player won
        if game.is_over:
            outcome = "USER_WON" if game.winner == "X" else "DRAW"
            outcome_res = await game_chat_bridge.process_game_outcome(
                game_name="XO", user_id=game.player_id, user_name=game.player_name, outcome=outcome, chat_id=game.chat_id
            )
            banner = f"🎉 <b>مبروك! فاز اللاعب {game.player_name} (❌)!</b> 🏆" if outcome == "USER_WON" else "🤝 <b>تعادل قوي ومثير!</b>"
            text = (
                f"❌⭕ <b>نهاية الجولة!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{banner}\n\n"
                f"💬 <b>عمر:</b> <i>{outcome_res.omar_retort}</i>"
            )
            return text, game.render_keyboard(game_id), "انتهت الجولة!"

        # Omar AI Move
        ai_idx = game.omar_ai_move()
        if ai_idx is not None:
            game.make_move(ai_idx, "O")

        if game.is_over:
            outcome = "OMAR_WON" if game.winner == "O" else "DRAW"
            outcome_res = await game_chat_bridge.process_game_outcome(
                game_name="XO", user_id=game.player_id, user_name=game.player_name, outcome=outcome, chat_id=game.chat_id
            )
            banner = f"👑 <b>فاز «عمر» (⭕)! هارد لك يا {game.player_name}</b> 😎" if outcome == "OMAR_WON" else "🤝 <b>تعادل قوي ومثير!</b>"
            text = (
                f"❌⭕ <b>نهاية الجولة!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{banner}\n\n"
                f"💬 <b>عمر:</b> <i>{outcome_res.omar_retort}</i>"
            )
            return text, game.render_keyboard(game_id), "انتهت الجولة!"

        text = (
            f"❌⭕ <b>لعبة إكس أو ضد عمر</b> 🎮\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>اللاعب:</b> {game.player_name} (❌)\n"
            f"🤖 <b>المنافس:</b> عمر (⭕)\n"
            f"<i>دورك الآن يا {game.player_name}، حط حركتك الذكية:</i>"
        )
        return text, game.render_keyboard(game_id), None

    def start_trivia_question(self, user_name: str) -> Tuple[str, Dict[str, Any]]:
        q = random.choice(TriviaBank.QUESTIONS)
        q_id = f"tr_{q['id']}_{int(time.time())}"
        self.active_trivia_questions[q_id] = q

        text = (
            f"🧠 <b>مسابقة بنك المعلومات والتحدي الثقافي</b> 🎯\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>القسم:</b> <i>{q['category']}</i>\n"
            f"❓ <b>السؤال:</b>\n"
            f"<b>{q['question']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>اختر الإجابة الصحيحة بالضغط على الزر:</i>"
        )
        buttons = []
        for idx, opt in enumerate(q["options"]):
            buttons.append([{"text": f"{idx+1}. {opt}", "callback_data": f"trivia:{q_id}:{idx}", "style": "primary"}])
        buttons.append([{"text": "🔄 سؤال آخر 🎲", "callback_data": "act:game_trivia", "style": "success"}])
        buttons.append([{"text": "🔙 ساحة الألعاب 🎮", "callback_data": "menu:games", "style": "danger"}])

        return text, {"inline_keyboard": buttons}

    async def handle_trivia_answer(
        self, q_id: str, selected_idx: int, user_id: int, user_name: str
    ) -> Tuple[str, Dict[str, Any], str]:
        q = self.active_trivia_questions.get(q_id)
        if not q:
            return "⚠️ انتهت صلاحية هذا السؤال. اضغط سؤال آخر للتحدي.", {"inline_keyboard": [[{"text": "🔄 سؤال جديد", "callback_data": "act:game_trivia"}]]}, "انتهى السؤال!"

        correct_idx = q["correct_index"]
        is_correct = selected_idx == correct_idx

        outcome = "TRIVIA_CORRECT" if is_correct else "TRIVIA_WRONG"
        outcome_res = await game_chat_bridge.process_game_outcome(
            game_name="Trivia", user_id=user_id, user_name=user_name, outcome=outcome
        )

        status_text = (
            f"✅ <b>إجابة صحيحة وممتازة يا {user_name}!</b> 🌟 (+30 نقطة معزة)\n"
            f"🎯 <b>الإجابة الصحيحة هي:</b> <b>{q['options'][correct_idx]}</b>"
            if is_correct
            else f"❌ <b>إجابة غير صحيحة يا {user_name}!</b> 😅\n"
            f"🎯 <b>الإجابة الصحيحة كانت:</b> <b>{q['options'][correct_idx]}</b>"
        )

        text = (
            f"🧠 <b>نتيجة التحدي الثقافي</b> 🎯\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❓ <b>السؤال:</b> {q['question']}\n\n"
            f"{status_text}\n\n"
            f"💬 <b>عمر:</b> <i>{outcome_res.omar_retort}</i>"
        )

        buttons = [
            [{"text": "🔄 سؤال جديد للتحدي 🎯", "callback_data": "act:game_trivia", "style": "success"}],
            [{"text": "🔙 ساحة الألعاب 🎮", "callback_data": "menu:games", "style": "primary"}],
        ]
        toast = "صح عليك! 🎉" if is_correct else "حظ أوفر المرة الجاية! 👏"
        return text, {"inline_keyboard": buttons}, toast

    async def play_rps(self, user_choice: str, user_id: int, user_name: str) -> Tuple[str, Dict[str, Any], str]:
        choices = ["rock", "paper", "scissors"]
        choice_icons = {"rock": "🪨 حجرة", "paper": "📄 ورقة", "scissors": "✂️ مقص"}
        omar_choice = random.choice(choices)

        if user_choice == omar_choice:
            result = "DRAW"
            result_text = "🤝 <b>تعادل! كلكما اخترتم نفس الشيء!</b>"
        elif (
            (user_choice == "rock" and omar_choice == "scissors")
            or (user_choice == "paper" and omar_choice == "rock")
            or (user_choice == "scissors" and omar_choice == "paper")
        ):
            result = "USER_WON"
            result_text = f"🎉 <b>فوز مستحق ليك يا {user_name}! كسبتني في الجولة دي!</b> 🏆"
        else:
            result = "OMAR_WON"
            result_text = f"😎 <b>فوز لـ «عُـمـر»! تفوقت عليك بحركة محكمة!</b> 🔥"

        outcome_res = await game_chat_bridge.process_game_outcome(
            game_name="RPS", user_id=user_id, user_name=user_name, outcome=result
        )

        text = (
            f"✊✋✌️ <b>لعبة حجرة ورقة مقص ضد عُمر</b> 🎲\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>اختيارك ({user_name}):</b> {choice_icons.get(user_choice, user_choice)}\n"
            f"🤖 <b>اختيار عمر:</b> {choice_icons.get(omar_choice, omar_choice)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{result_text}\n\n"
            f"💬 <b>عمر:</b> <i>{outcome_res.omar_retort}</i>"
        )

        buttons = [
            [
                {"text": "🪨 حجرة", "callback_data": "rps:rock", "style": "primary"},
                {"text": "📄 ورقة", "callback_data": "rps:paper", "style": "primary"},
                {"text": "✂️ مقص", "callback_data": "rps:scissors", "style": "primary"},
            ],
            [{"text": "🔙 ساحة الألعاب 🎮", "callback_data": "menu:games", "style": "danger"}],
        ]
        return text, {"inline_keyboard": buttons}, "اكتملت الجولة!"


group_games = GroupGamesEngine()

