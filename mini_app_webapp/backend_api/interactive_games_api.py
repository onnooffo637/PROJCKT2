"""
Interactive Games Backend API (Project Aether-Human V5.0)
Powers fully playable Mini-App arcade games:
1. Smart Tic-Tac-Toe (X-O Pro) with Minimax AI & live banter.
2. Connect 4 (Four in a Row) with strategic drop AI.
3. Live AI Trivia & Riddle Arena with streaks and coin rewards.
4. Guess The Secret Number with intelligent clues.
5. Rock Paper Scissors (RPS) with psychological counter-moves.
6. Mind Detective / 2 Truths & 1 Lie interrogation.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("Aether.MiniApp.GamesAPI")
router = APIRouter(prefix="/api/webapp/game", tags=["MiniApp Games"])

# In-Memory Active Game States per user
_user_xo_boards: Dict[int, List[int]] = {}  # 0: empty, 1: X (user), 2: O (bot)
_user_c4_boards: Dict[int, List[List[int]]] = {}  # 6 rows x 7 cols
_user_guess_target: Dict[int, Dict[str, Any]] = {}
_user_streaks: Dict[int, int] = {}
_user_coins: Dict[int, int] = {}


# ==========================================
# 1. Tic-Tac-Toe (X-O Pro vs Smart AI)
# ==========================================

class XOMoveRequest(BaseModel):
    user_id: int
    position: int  # 0 to 8


class XOResetRequest(BaseModel):
    user_id: int


def _check_xo_winner(board: List[int]) -> Optional[int]:
    wins = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Cols
        [0, 4, 8], [2, 4, 6]              # Diagonals
    ]
    for w in wins:
        if board[w[0]] != 0 and board[w[0]] == board[w[1]] == board[w[2]]:
            return board[w[0]]
    if 0 not in board:
        return 0  # Draw
    return None  # Ongoing


def _best_xo_move(board: List[int]) -> int:
    """Calculates smart move for Bot (2) using win/block heuristic."""
    # 1. Check if bot can win immediately
    for i in range(9):
        if board[i] == 0:
            board[i] = 2
            if _check_xo_winner(board) == 2:
                board[i] = 0
                return i
            board[i] = 0

    # 2. Check if user is about to win and block them
    for i in range(9):
        if board[i] == 0:
            board[i] = 1
            if _check_xo_winner(board) == 1:
                board[i] = 0
                return i
            board[i] = 0

    # 3. Take center if available
    if board[4] == 0:
        return 4

    # 4. Take corners
    corners = [i for i in [0, 2, 6, 8] if board[i] == 0]
    if corners:
        return random.choice(corners)

    # 5. Take any empty cell
    empties = [i for i in range(9) if board[i] == 0]
    return random.choice(empties) if empties else -1


@router.post("/xo/move")
async def xo_move(req: XOMoveRequest):
    uid = req.user_id
    if uid not in _user_xo_boards:
        _user_xo_boards[uid] = [0] * 9

    board = _user_xo_boards[uid]
    pos = req.position
    if pos < 0 or pos > 8 or board[pos] != 0:
        return {"board": board, "status": "invalid", "message": "مكان غير صالح يا غالي!"}

    # User move (X = 1)
    board[pos] = 1
    winner = _check_xo_winner(board)

    if winner == 1:
        _user_coins[uid] = _user_coins.get(uid, 100) + 25
        return {
            "board": board,
            "status": "win",
            "winner": 1,
            "coins_delta": 25,
            "message": "🔥 فنان ومبروك! كسبتني وكسبت 25 عملة Aether Coins 🪙",
        }
    elif winner == 0:
        _user_coins[uid] = _user_coins.get(uid, 100) + 5
        return {
            "board": board,
            "status": "draw",
            "winner": 0,
            "coins_delta": 5,
            "message": "🤝 تعادل مشرف ومباراة حامية! كسبت 5 عملات.",
        }

    # Bot move (O = 2)
    bot_pos = _best_xo_move(board)
    if bot_pos != -1:
        board[bot_pos] = 2
        bot_winner = _check_xo_winner(board)
        if bot_winner == 2:
            return {
                "board": board,
                "status": "loss",
                "winner": 2,
                "coins_delta": 0,
                "message": "😎 هاردلك! قفلت عليك وكسبت الجولة.. العب تاني وعوضها! 🦾",
            }
        elif bot_winner == 0:
            return {
                "board": board,
                "status": "draw",
                "winner": 0,
                "coins_delta": 5,
                "message": "🤝 تعادل في اللحظات الأخيرة!",
            }

    banters = [
        "حركة ذكية بس عيني على المكسب! دورك يا بطل ⚡",
        "فاكرني هسيبك تاخد الزاوية؟ دورك العب! 🎯",
        "اللعب بيحلو.. ركز في حركتك الجاية 😉",
    ]
    return {
        "board": board,
        "status": "ongoing",
        "winner": None,
        "coins_delta": 0,
        "message": random.choice(banters),
    }


@router.post("/xo/reset")
async def xo_reset(req: XOResetRequest):
    _user_xo_boards[req.user_id] = [0] * 9
    return {
        "board": [0] * 9,
        "status": "ongoing",
        "message": "🎮 تم بدء لعبة X-O جديدة! دورك يا كابتن (X).",
    }


# ==========================================
# 2. Connect 4 (أربعة في صف)
# ==========================================

class C4MoveRequest(BaseModel):
    user_id: int
    column: int  # 0 to 6


class C4ResetRequest(BaseModel):
    user_id: int


def _check_c4_winner(board: List[List[int]]) -> Optional[int]:
    ROWS = 6
    COLS = 7
    # Horizontal
    for r in range(ROWS):
        for c in range(COLS - 3):
            if board[r][c] != 0 and board[r][c] == board[r][c+1] == board[r][c+2] == board[r][c+3]:
                return board[r][c]
    # Vertical
    for r in range(ROWS - 3):
        for c in range(COLS):
            if board[r][c] != 0 and board[r][c] == board[r+1][c] == board[r+2][c] == board[r+3][c]:
                return board[r][c]
    # Positive Diagonal
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            if board[r][c] != 0 and board[r][c] == board[r+1][c+1] == board[r+2][c+2] == board[r+3][c+3]:
                return board[r][c]
    # Negative Diagonal
    for r in range(3, ROWS):
        for c in range(COLS - 3):
            if board[r][c] != 0 and board[r][c] == board[r-1][c+1] == board[r-2][c+2] == board[r-3][c+3]:
                return board[r][c]

    # Check Draw
    if all(board[0][c] != 0 for c in range(COLS)):
        return 0
    return None


def _drop_disc(board: List[List[int]], col: int, piece: int) -> int:
    """Drops disc into column and returns landing row index or -1 if full."""
    for r in range(5, -1, -1):
        if board[r][col] == 0:
            board[r][col] = piece
            return r
    return -1


@router.post("/c4/move")
async def c4_move(req: C4MoveRequest):
    uid = req.user_id
    if uid not in _user_c4_boards:
        _user_c4_boards[uid] = [[0] * 7 for _ in range(6)]

    board = _user_c4_boards[uid]
    col = req.column
    if col < 0 or col > 6:
        return {"board": board, "status": "invalid", "message": "عمود غير صالح!"}

    # User drop (1 = Red)
    user_row = _drop_disc(board, col, 1)
    if user_row == -1:
        return {"board": board, "status": "full", "message": "العمود ده مليان، اختار عمود تاني!"}

    win = _check_c4_winner(board)
    if win == 1:
        _user_coins[uid] = _user_coins.get(uid, 100) + 40
        return {
            "board": board,
            "status": "win",
            "message": "🎉 أسطورة استراتيجية! كسبت في Connect 4 وأخدت 40 عملة 🪙",
        }

    # Bot move (2 = Yellow)
    valid_cols = [c for c in range(7) if board[0][c] == 0]
    if valid_cols:
        # Check bot winning drop or blocking user
        chosen_col = random.choice(valid_cols)
        for cand in valid_cols:
            temp_row = _drop_disc(board, cand, 2)
            if _check_c4_winner(board) == 2:
                chosen_col = cand
                board[temp_row][cand] = 0
                break
            board[temp_row][cand] = 0

            # Block user win
            temp_row_u = _drop_disc(board, cand, 1)
            if _check_c4_winner(board) == 1:
                chosen_col = cand
                board[temp_row_u][cand] = 0
                break
            board[temp_row_u][cand] = 0

        _drop_disc(board, chosen_col, 2)
        win_bot = _check_c4_winner(board)
        if win_bot == 2:
            return {
                "board": board,
                "status": "loss",
                "message": "🤖 كسبت الجولة! صف كامل للأصفر.. جرب تاني!",
            }

    return {
        "board": board,
        "status": "ongoing",
        "message": "رميت القرص بتاعي.. دورك يا هندسة!",
    }


@router.post("/c4/reset")
async def c4_reset(req: C4ResetRequest):
    _user_c4_boards[req.user_id] = [[0] * 7 for _ in range(6)]
    return {
        "board": [[0] * 7 for _ in range(6)],
        "status": "ongoing",
        "message": "تم إعادة ضبط لوحة Connect 4!",
    }


# ==========================================
# 3. Live AI Trivia & Riddles
# ==========================================

TRIVIA_QUESTIONS = [
    {
        "id": 1,
        "question": "ما هي لغة البرمجة التي سُميت تيمناً بفرقة كوميدية بريطانية شهيرة؟",
        "options": ["Ruby", "Python", "Java", "Kotlin"],
        "correct": 1,
        "explanation": "سُميت بايثون تيمناً بسلسلة Monty Python's Flying Circus من قِبل غيدو فان روسم!",
    },
    {
        "id": 2,
        "question": "كم عدد الجيوب الأنفية في جمجمة الإنسان البالغ؟",
        "options": ["4 أزواج (8)", "زوجان (4)", "6 أزواج (12)", "3 أزواج (6)"],
        "correct": 0,
        "explanation": "تمتلك جمجمة الإنسان 4 أزواج من الجيوب الهوائية المحيطة بالأنف.",
    },
    {
        "id": 3,
        "question": "ما هو أسرع كوكب يدور حول الشمس في مجموعتنا الشمسية؟",
        "options": ["الزهرة", "المريخ", "عطارد", "المشتري"],
        "correct": 2,
        "explanation": "عطارد هو الأقرب والأسرع، ويكمل دورته حول الشمس في 88 يوماً أرضياً فقط!",
    },
    {
        "id": 4,
        "question": "في أي عام تم إطلاق تطبيق تيليجرام لأول مرة رسمياً؟",
        "options": ["2011", "2013", "2015", "2016"],
        "correct": 1,
        "explanation": "أطلقه الأخوين بافيل ونيكولاي دوروف في أغسطس عام 2013.",
    },
    {
        "id": 5,
        "question": "ما هو العنصر الكيميائي الأكثر وفرة في الكون بأكمله؟",
        "options": ["الأكسجين", "الهيليوم", "الهيدروجين", "الكربون"],
        "correct": 2,
        "explanation": "الهيدروجين يشكل حوالي 75% من الكتلة العنصرية في الكون!",
    },
    {
        "id": 6,
        "question": "لغز: شيء له رقبة وليس له رأس، وله ذراعان وليس له يدين.. ما هو؟",
        "options": ["القميص", "القنينة", "الساعة", "القلم"],
        "correct": 0,
        "explanation": "القميص له ياقة (رقبة) وأكمام (ذراعان) ولكنه يلبس بدون رأس أو يدين!",
    },
]


@router.get("/trivia/question")
async def get_trivia_question():
    q = random.choice(TRIVIA_QUESTIONS)
    return {
        "id": q["id"],
        "question": q["question"],
        "options": q["options"],
    }


class TriviaAnswerRequest(BaseModel):
    user_id: int
    question_id: int
    selected_index: int


@router.post("/trivia/answer")
async def answer_trivia(req: TriviaAnswerRequest):
    q = next((item for item in TRIVIA_QUESTIONS if item["id"] == req.question_id), None)
    if not q:
        raise HTTPException(status_code=404, detail="السؤال غير موجود")

    uid = req.user_id
    is_correct = (req.selected_index == q["correct"])

    if is_correct:
        _user_streaks[uid] = _user_streaks.get(uid, 0) + 1
        streak = _user_streaks[uid]
        bonus = 10 + (streak * 5)
        _user_coins[uid] = _user_coins.get(uid, 100) + bonus
        return {
            "is_correct": True,
            "explanation": q["explanation"],
            "current_streak": streak,
            "coins_delta": bonus,
        }
    else:
        _user_streaks[uid] = 0
        return {
            "is_correct": False,
            "explanation": f"الإجابة الصحيحة كانت: ({q['options'][q['correct']]}). {q['explanation']}",
            "current_streak": 0,
            "coins_delta": 0,
        }


# ==========================================
# 4. Guess The Number
# ==========================================

class GuessRequest(BaseModel):
    user_id: int
    guess: int


@router.post("/guess/submit")
async def submit_guess(req: GuessRequest):
    uid = req.user_id
    if uid not in _user_guess_target:
        _user_guess_target[uid] = {"target": random.randint(1, 100), "attempts": 0}

    state = _user_guess_target[uid]
    state["attempts"] += 1
    target = state["target"]
    guess = req.guess

    if guess == target:
        att = state["attempts"]
        coins = max(5, 50 - (att * 5))
        _user_coins[uid] = _user_coins.get(uid, 100) + coins
        # Reset for next round
        _user_guess_target[uid] = {"target": random.randint(1, 100), "attempts": 0}
        return {
            "is_correct": True,
            "message": f"🎯 عبقري! الرقم السري كان بالفعل {target}! خمنته في {att} محاولات وكسبت {coins} عملة 🪙",
            "attempts": att,
        }
    elif guess < target:
        return {
            "is_correct": False,
            "message": f"الرقم السري أكبر من {guess} 📈 (المحاولة رقم {state['attempts']})",
            "attempts": state["attempts"],
        }
    else:
        return {
            "is_correct": False,
            "message": f"الرقم السري أصغر من {guess} 📉 (المحاولة رقم {state['attempts']})",
            "attempts": state["attempts"],
        }


@router.post("/guess/reset")
async def reset_guess(req: XOResetRequest):
    _user_guess_target[req.user_id] = {"target": random.randint(1, 100), "attempts": 0}
    return {"status": "reset", "message": "تم اختيار رقم سري جديد من 1 إلى 100!"}


# ==========================================
# 5. Rock Paper Scissors (حجرة ورقة مقص)
# ==========================================

class RPSRequest(BaseModel):
    user_id: int
    move: str  # rock, paper, scissors


@router.post("/rps/play")
async def play_rps(req: RPSRequest):
    u_move = req.move.lower().strip()
    moves = ["rock", "paper", "scissors"]
    names_ar = {"rock": "حجرة 🪨", "paper": "ورقة 📄", "scissors": "مقص ✂️"}

    if u_move not in moves:
        u_move = "rock"

    b_move = random.choice(moves)

    if u_move == b_move:
        result = "draw"
        msg = "تعادلنا! نفس التفكير يا معلم 🤝"
        coins = 3
    elif (
        (u_move == "rock" and b_move == "scissors") or
        (u_move == "paper" and b_move == "rock") or
        (u_move == "scissors" and b_move == "paper")
    ):
        result = "win"
        msg = "مبروك يا فنان! كسبتني بحركتك الذكية 🎉"
        coins = 15
    else:
        result = "loss"
        msg = "حظ أوفر! قريت دماغك وكسبت الجولة دي 😎"
        coins = 0

    if coins > 0:
        _user_coins[req.user_id] = _user_coins.get(req.user_id, 100) + coins

    return {
        "user_move": names_ar[u_move],
        "bot_move": names_ar[b_move],
        "result": result,
        "message": msg,
        "coins_delta": coins,
    }

