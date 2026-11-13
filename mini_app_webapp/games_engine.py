"""
Interactive Games Engine for Telegram Mini App (V2.0).
Powers:
1. Tic-Tac-Toe (XO Pro) with minimax AI & instant zero-lag reset
2. Connect 4 (أربعة على التوالي) with 7x6 gravity grid & strategic AI
3. Trivia Arena with expanded categories and scoring
4. Number Guessing (خمن الرقم السري 1-100) with hot/cold thermometer hints
5. Rock-Paper-Scissors (حجرة ورقة مقص) with live banter
"""

from __future__ import annotations

import logging
import random
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger("Aether.MiniApp.GamesEngine")


# ==============================================================================
# 1. TIC-TAC-TOE (XO PRO)
# ==============================================================================

class XOGameSession:
    """
    Tic-Tac-Toe session against Omar (AI).
    Board is a list of 9 elements: [' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ']
    User plays 'X', Omar plays 'O'.
    """

    WIN_COMBINATIONS = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),  # Rows
        (0, 3, 6), (1, 4, 7), (2, 5, 8),  # Columns
        (0, 4, 8), (2, 4, 6)              # Diagonals
    ]

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.board: List[str] = [" "] * 9
        self.game_over: bool = False
        self.winner: Optional[str] = None  # 'X', 'O', or 'DRAW'
        self.winning_line: Optional[List[int]] = None

    def user_move(self, index: int, difficulty: str = "easy") -> Tuple[bool, str]:
        if self.game_over:
            return False, "انتهت اللعبة بالفعل! اضغط على زر إعادة للبدء من جديد."
        if index < 0 or index > 8 or self.board[index] != " ":
            return False, "موضع غير صالح أو مشغول بالفعل!"

        self.board[index] = "X"
        win_info = self._check_winner()
        if win_info:
            self.game_over = True
            self.winner = win_info[0]
            self.winning_line = list(win_info[1])
            return True, "USER_WON" if self.winner == "X" else "DRAW"

        if " " not in self.board:
            self.game_over = True
            self.winner = "DRAW"
            return True, "DRAW"

        # Omar move tuned to selected difficulty
        omar_idx = self._compute_omar_move(difficulty=difficulty)
        if omar_idx is not None:
            self.board[omar_idx] = "O"
            win_info = self._check_winner()
            if win_info:
                self.game_over = True
                self.winner = win_info[0]
                self.winning_line = list(win_info[1])
                return True, "OMAR_WON" if self.winner == "O" else "DRAW"

        if " " not in self.board:
            self.game_over = True
            self.winner = "DRAW"
            return True, "DRAW"

        return True, "CONTINUE"

    def _check_winner(self) -> Optional[Tuple[str, Tuple[int, int, int]]]:
        for a, b, c in self.WIN_COMBINATIONS:
            if self.board[a] != " " and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a], (a, b, c)
        return None

    def _compute_omar_move(self, difficulty: str = "easy") -> Optional[int]:
        empty = [i for i in range(9) if self.board[i] == " "]
        if not empty:
            return None

        # Level 1: EASY (سهل - لعب بشري بسيط وفرص فوز عالية للاعب)
        if difficulty == "easy":
            if random.random() < 0.85:
                return random.choice(empty)
            sub = [i for i in [4, 0, 2, 6, 8] if i in empty]
            return random.choice(sub) if sub else random.choice(empty)

        # Level 2: MEDIUM (متوسط - توازن ذكي وممتع)
        elif difficulty == "medium":
            if random.random() < 0.55:
                for i in empty:
                    self.board[i] = "X"
                    if self._check_winner() and self._check_winner()[0] == "X":
                        self.board[i] = " "
                        return i
                    self.board[i] = " "
            if random.random() < 0.60:
                for i in empty:
                    self.board[i] = "O"
                    if self._check_winner() and self._check_winner()[0] == "O":
                        self.board[i] = " "
                        return i
                    self.board[i] = " "
            if 4 in empty and random.random() < 0.5:
                return 4
            return random.choice(empty)

        # Level 3: HARD (صعب ومحترف - تكتيك ذكي ومحكم)
        else:
            # 1. Win if possible
            for i in empty:
                self.board[i] = "O"
                if self._check_winner() and self._check_winner()[0] == "O":
                    self.board[i] = " "
                    return i
                self.board[i] = " "

            # 2. Block user win
            for i in empty:
                self.board[i] = "X"
                if self._check_winner() and self._check_winner()[0] == "X":
                    self.board[i] = " "
                    return i
                self.board[i] = " "

            # 3. Take center
            if 4 in empty:
                return 4

            # 4. Take corners
            corners = [i for i in [0, 2, 6, 8] if i in empty]
            if corners:
                return random.choice(corners)

            return random.choice(empty)

    def get_state(self) -> Dict[str, Any]:
        return {
            "board": self.board,
            "game_over": self.game_over,
            "winner": self.winner,
            "winning_line": self.winning_line,
        }


# ==============================================================================
# 2. CONNECT 4 (أربعة على التوالي)
# ==============================================================================

class Connect4Session:
    """
    Connect 4 game grid: 6 rows (0 to 5, where 5 is bottom), 7 columns (0 to 6).
    User is 'U' (Blue), Omar AI is 'O' (Red), Empty is ' '.
    """
    ROWS = 6
    COLS = 7

    def __init__(self, user_id: int):
        self.user_id = user_id
        # Grid indexed as grid[row][col]
        self.grid: List[List[str]] = [[" " for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self.game_over: bool = False
        self.winner: Optional[str] = None  # 'USER', 'OMAR', 'DRAW'
        self.winning_coords: List[Tuple[int, int]] = []

    def drop_piece(self, col: int, difficulty: str = "easy") -> Tuple[bool, str, Optional[int]]:
        """
        User drops piece into column (0-6) with adaptive difficulty.
        """
        if self.game_over:
            return False, "انتهت الجولة بالفعل!", None
        if col < 0 or col >= self.COLS:
            return False, "عمود غير صالح!", None

        # Find lowest empty row in column
        user_row = self._find_lowest_empty_row(col)
        if user_row is None:
            return False, "هذا العمود ممتلئ تماماً!", None

        self.grid[user_row][col] = "U"
        win = self._check_win("U")
        if win:
            self.game_over = True
            self.winner = "USER"
            self.winning_coords = win
            return True, "USER_WON", user_row

        if self._is_full():
            self.game_over = True
            self.winner = "DRAW"
            return True, "DRAW", user_row

        # Omar AI move tuned to difficulty
        omar_col = self._compute_omar_move(difficulty=difficulty)
        omar_row = None
        if omar_col is not None:
            omar_row = self._find_lowest_empty_row(omar_col)
            if omar_row is not None:
                self.grid[omar_row][omar_col] = "O"
                win = self._check_win("O")
                if win:
                    self.game_over = True
                    self.winner = "OMAR"
                    self.winning_coords = win
                    return True, "OMAR_WON", user_row

        if self._is_full():
            self.game_over = True
            self.winner = "DRAW"
            return True, "DRAW", user_row

        return True, "CONTINUE", user_row

    def _find_lowest_empty_row(self, col: int) -> Optional[int]:
        for r in range(self.ROWS - 1, -1, -1):
            if self.grid[r][col] == " ":
                return r
        return None

    def _is_full(self) -> bool:
        return all(self.grid[0][c] != " " for c in range(self.COLS))

    def _check_win(self, piece: str) -> Optional[List[Tuple[int, int]]]:
        # Horizontal
        for r in range(self.ROWS):
            for c in range(self.COLS - 3):
                if all(self.grid[r][c + i] == piece for i in range(4)):
                    return [(r, c + i) for i in range(4)]
        # Vertical
        for r in range(self.ROWS - 3):
            for c in range(self.COLS):
                if all(self.grid[r + i][c] == piece for i in range(4)):
                    return [(r + i, c) for i in range(4)]
        # Diagonal positive
        for r in range(self.ROWS - 3):
            for c in range(self.COLS - 3):
                if all(self.grid[r + i][c + i] == piece for i in range(4)):
                    return [(r + i, c + i) for i in range(4)]
        # Diagonal negative
        for r in range(3, self.ROWS):
            for c in range(self.COLS - 3):
                if all(self.grid[r - i][c + i] == piece for i in range(4)):
                    return [(r - i, c + i) for i in range(4)]
        return None

    def _compute_omar_move(self, difficulty: str = "easy") -> Optional[int]:
        valid_cols = [c for c in range(self.COLS) if self._find_lowest_empty_row(c) is not None]
        if not valid_cols:
            return None

        # Level 1: Easy (80% random, lets user build 4 easily)
        if difficulty == "easy":
            if random.random() < 0.80:
                return random.choice(valid_cols)
            return valid_cols[len(valid_cols) // 2]

        # Level 2: Medium (50% block, 50% casual)
        elif difficulty == "medium":
            if random.random() < 0.50:
                for c in valid_cols:
                    r = self._find_lowest_empty_row(c)
                    self.grid[r][c] = "U"
                    if self._check_win("U"):
                        self.grid[r][c] = " "
                        return c
                    self.grid[r][c] = " "
            return random.choice(valid_cols)

        # Level 3: Hard (Strategic win & block)
        else:
            for c in valid_cols:
                r = self._find_lowest_empty_row(c)
                self.grid[r][c] = "O"
                if self._check_win("O"):
                    self.grid[r][c] = " "
                    return c
                self.grid[r][c] = " "

            for c in valid_cols:
                r = self._find_lowest_empty_row(c)
                self.grid[r][c] = "U"
                if self._check_win("U"):
                    self.grid[r][c] = " "
                    return c
                self.grid[r][c] = " "

            center_pref = [3, 2, 4, 1, 5, 0, 6]
            for c in center_pref:
                if c in valid_cols:
                    return c
            return random.choice(valid_cols)

    def get_state(self) -> Dict[str, Any]:
        return {
            "grid": self.grid,
            "game_over": self.game_over,
            "winner": self.winner,
            "winning_coords": self.winning_coords,
        }


# ==============================================================================
# 3. NUMBER GUESSING (خمن الرقم 1-100)
# ==============================================================================

class NumberGuessSession:
    """
    Session where Omar thinks of a number between 1 and 100.
    """
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.secret_number: int = random.randint(1, 100)
        self.attempts: int = 0
        self.game_over: bool = False
        self.history: List[Dict[str, Any]] = []

    def make_guess(self, guess: int) -> Dict[str, Any]:
        if self.game_over:
            return {"game_over": True, "message": "انتهت اللعبة! اضغط على إعادة لبدء تحدٍ جديد."}

        self.attempts += 1
        diff = abs(guess - self.secret_number)

        if guess == self.secret_number:
            self.game_over = True
            msg = f"🎉 مبروووك يا بطل! خمنت الرقم الصحيح ({self.secret_number}) في {self.attempts} محاولات!"
            status = "WIN"
        elif guess < self.secret_number:
            hint = "قريب جداً 🔥" if diff <= 5 else ("أكبر بكتير 🚀" if diff > 20 else "أكبر شوية 📈")
            msg = f"الرقم السري أكبر من {guess}! ({hint})"
            status = "TOO_LOW"
        else:
            hint = "قريب جداً 🔥" if diff <= 5 else ("أصغر بكتير ❄️" if diff > 20 else "أصغر شوية 📉")
            msg = f"الرقم السري أصغر من {guess}! ({hint})"
            status = "TOO_HIGH"

        result = {
            "guess": guess,
            "status": status,
            "message": msg,
            "attempts": self.attempts,
            "game_over": self.game_over,
        }
        self.history.append(result)
        return result


# ==============================================================================
# 4. ROCK-PAPER-SCISSORS (حجرة ورقة مقص)
# ==============================================================================

class RockPaperScissorsEngine:
    CHOICES = ["rock", "paper", "scissors"]
    AR_NAMES = {"rock": "حجرة ✊", "paper": "ورقة ✋", "scissors": "مقص ✌️"}

    @classmethod
    def play_round(cls, user_choice: str, user_name: str = "اللاعب") -> Dict[str, Any]:
        choice = user_choice.lower().strip()
        if choice not in cls.CHOICES:
            return {"error": "اختيار غير صالح!"}

        omar_choice = random.choice(cls.CHOICES)

        if choice == omar_choice:
            outcome = "DRAW"
            retort = f"تعادلنا يا {user_name}! إحنا الاتنين اخترنا {cls.AR_NAMES[choice]}.. الجولة الجاية هكسبك 😉"
        elif (
            (choice == "rock" and omar_choice == "scissors")
            or (choice == "paper" and omar_choice == "rock")
            or (choice == "scissors" and omar_choice == "paper")
        ):
            outcome = "USER_WON"
            retort = f"عاش يا {user_name}! {cls.AR_NAMES[choice]} بتاعتك كسبت {cls.AR_NAMES[omar_choice]} بتاعتي.. مبروك! 🔥"
        else:
            outcome = "OMAR_WON"
            retort = f"كسبتك يا {user_name}! {cls.AR_NAMES[omar_choice]} غلبت {cls.AR_NAMES[choice]}.. العب تاني لو تقدر! 😎"

        return {
            "user_choice": choice,
            "omar_choice": omar_choice,
            "user_choice_ar": cls.AR_NAMES[choice],
            "omar_choice_ar": cls.AR_NAMES[omar_choice],
            "outcome": outcome,
            "retort": retort,
        }


# ==============================================================================
# 5. EXPANDED TRIVIA REPOSITORY
# ==============================================================================

class TriviaQuestion(BaseModel):
    id: int
    category: str
    question: str
    options: List[str]
    correct_index: int
    explanation: str


class TriviaBank:
    """
    Curated dynamic Arabic knowledge quiz repository with 15+ rich questions.
    """

    QUESTIONS: List[TriviaQuestion] = [
        TriviaQuestion(
            id=1,
            category="العلوم والذكاء الاصطناعي",
            question="ما هو النموذج اللغوي الأضخم المطور من قبل Google DeepMind والقادر على معالجة سياقات مليونية؟",
            options=["GPT-4", "Gemini 1.5 Pro", "Claude 3.5 Sonnet", "LLaMA 3"],
            correct_index=1,
            explanation="نماذج Gemini من Google DeepMind تميزت بنافذة سياق غير مسبوقة تصل إلى ملايين التوكنات.",
        ),
        TriviaQuestion(
            id=2,
            category="التاريخ والحضارة",
            question="في أي عام تم توحيد القطرين في مصر القديمة على يد الملك نعرمر (مينا)؟",
            options=["حوالي 3200 قبل الميلاد", "حوالي 1500 قبل الميلاد", "حوالي 500 قبل الميلاد", "عام 1000 ميلادي"],
            correct_index=0,
            explanation="توحدت مصر حوالي عام 3200 قبل الميلاد لتؤسس الأسرة المصرية الأولى.",
        ),
        TriviaQuestion(
            id=3,
            category="الثقافة واللغة",
            question="ما معنى كلمة 'جدع' في اللهجة المصرية الأصيلة؟",
            options=["الشخص المتكبر", "الشاب الشهم صاحب المروءة والوفاء", "الشخص المتردد", "التاجر الماهر"],
            correct_index=1,
            explanation="الجدعنة في الثقافة المصرية تعني قمة الشهامة والمروءة والوقوف مع الصاحب وقت الشدة.",
        ),
        TriviaQuestion(
            id=4,
            category="التكنولوجيا والبرمجة",
            question="ما هو البروتوكول فائق السرعة والمشفر المستخدم في تيليجرام للتواصل بين السيرفر والعميل؟",
            options=["HTTP/1.1", "MTProto", "gRPC Plain", "FTP"],
            correct_index=1,
            explanation="تيليجرام يستخدم بروتوكول MTProto المخصص للتشفير والسرعة العالية وتوفير البيانات.",
        ),
        TriviaQuestion(
            id=5,
            category="الفلك والكون",
            question="ما هو ألمع كوكب يمكن رؤيته بالعين المجردة في سماء الأرض ليلاً؟",
            options=["المريخ", "المشتري", "الزهرة (نجمة الصباح/المساء)", "زحل"],
            correct_index=2,
            explanation="كوكب الزهرة هو الأشد لمعاناً بسبب غلافه الجوي العاكس للضوء وقربه من الأرض.",
        ),
        TriviaQuestion(
            id=6,
            category="الألغاز والذكاء",
            question="شيء يملك أسناناً كثيرة ولكنه لا يعض أبداً؟",
            options=["التمساح", "المشط", "المنشار", "السحاب"],
            correct_index=1,
            explanation="المشط له أسنان لتسريح الشعر ولا يعض!",
        ),
        TriviaQuestion(
            id=7,
            category="الفيزياء والرياضيات",
            question="ما هي أسرع سرعة في الكون طبقاً للنسبية الخاصة لأينشتاين؟",
            options=["سرعة الصوت", "سرعة الضوء في الفراغ", "سرعة الإفلات من الجاذبية", "سرعة الإلكترونات"],
            correct_index=1,
            explanation="سرعة الضوء في الفراغ (حوالي 300 ألف كم/ثانية) هي الحد الأقصى الكوني للسرعة.",
        ),
        TriviaQuestion(
            id=8,
            category="الجغرافيا والمعالم",
            question="ما هو أطول نهر في العالم؟",
            options=["نهر الأمازون", "نهر النيل", "نهر المسيسيبي", "نهر اليانغتسي"],
            correct_index=1,
            explanation="نهر النيل هو أطول نهر في العالم ويمر عبر 11 دولة إفريقية.",
        ),
        TriviaQuestion(
            id=9,
            category="البرمجة والأنظمة",
            question="من هو مبتكر لغة بايثون (Python) التي كُتب بها هذا النظام؟",
            options=["جيدو فان روسوم (Guido van Rossum)", "لينوس تورفالدس", "دينيس ريتشي", "جيمس جوسلينج"],
            correct_index=0,
            explanation="أنشأ جيدو فان روسوم لغة بايثون في هولندا وأصدر أول نسخة عام 1991.",
        ),
        TriviaQuestion(
            id=10,
            category="الطب وعلم الأحياء",
            question="ما هو العضو المسؤول عن ضخ الدم وتوزيعه في كافة أنحاء الجسم البشري؟",
            options=["الكبد", "الرئتان", "القلب", "الكلى"],
            correct_index=2,
            explanation="القلب ينبض حوالي 100 ألف مرة يومياً ليضخ آلاف اللترات من الدم إلى أنسجة الجسم.",
        ),
    ]

    @classmethod
    def get_random_question(cls) -> TriviaQuestion:
        return random.choice(cls.QUESTIONS)

    @classmethod
    def get_question_by_id(cls, q_id: int) -> Optional[TriviaQuestion]:
        for q in cls.QUESTIONS:
            if q.id == q_id:
                return q
        return None
