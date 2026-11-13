r"""
Human-Readable Mathematical Formatter & LaTeX Sanitizer for Project Aether-Human.
Transforms raw, ugly, mechanical LaTeX expressions (\(, \[, \frac, \sqrt) into
clean, elegant, human-readable Unicode mathematical expressions for Telegram.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# Superscript mapping
SUPERSCRIPTS: Dict[str, str] = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "n": "ⁿ", "i": "ⁱ", "x": "ˣ", "y": "ʸ"
}

# Subscript mapping
SUBSCRIPTS: Dict[str, str] = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "o": "ₒ", "x": "ₓ", "i": "ᵢ", "j": "ⱼ"
}

# Greek and math symbols mapping
LATEX_SYMBOLS: Dict[str, str] = {
    r"\pm": "±",
    r"\mp": "∓",
    r"\times": " × ",
    r"\cdot": " • ",
    r"\div": " ÷ ",
    r"\leq": " ≤ ",
    r"\le": " ≤ ",
    r"\geq": " ≥ ",
    r"\ge": " ≥ ",
    r"\neq": " ≠ ",
    r"\ne": " ≠ ",
    r"\approx": " ≈ ",
    r"\sim": " ~ ",
    r"\equiv": " ≡ ",
    r"\infty": "∞",
    r"\pi": "π",
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\delta": "δ",
    r"\Delta": "Δ",
    r"\epsilon": "ε",
    r"\theta": "θ",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\sigma": "σ",
    r"\Sigma": "∑",
    r"\sum": "∑",
    r"\int": "∫",
    r"\partial": "∂",
    r"\nabla": "∇",
    r"\degree": "°",
    r"\circ": "°",
    r"\rightarrow": " → ",
    r"\leftarrow": " ← ",
    r"\Rightarrow": " ⇒ ",
    r"\Leftarrow": " ⇐ ",
    r"\Leftrightarrow": " ⇔ ",
    r"\forall": "∀",
    r"\exists": "∃",
    r"\in": " ∈ ",
    r"\notin": " ∉ ",
    r"\subset": " ⊂ ",
    r"\subseteq": " ⊆ ",
    r"\cup": " ∪ ",
    r"\cap": " ∩ ",
}


class HumanMathFormatter:
    """
    Sanitizes and converts LaTeX math into human-friendly Unicode equations.
    """

    @staticmethod
    def _extract_braced(s: str, pos: int) -> Tuple[Optional[str], int]:
        """Extracts content inside balanced curly braces {...} starting at pos."""
        if pos >= len(s) or s[pos] != '{':
            return None, pos
        depth = 1
        idx = pos + 1
        start = idx
        while idx < len(s) and depth > 0:
            if s[idx] == '{':
                depth += 1
            elif s[idx] == '}':
                depth -= 1
            idx += 1
        if depth == 0:
            return s[start:idx - 1], idx
        return None, pos

    @classmethod
    def format_math_text(cls, text: str) -> str:
        """
        Main entrypoint: cleans any LaTeX equations embedded in the text.
        """
        if not text:
            return ""

        result = text

        # 1. Strip raw LaTeX delimiters: \( ... \) and \[ ... \] and $$ ... $$ and $ ... $
        result = re.sub(r"\\\[\s*(.*?)\s*\\\]", r"\n\1\n", result, flags=re.DOTALL)
        result = re.sub(r"\\\(\s*(.*?)\s*\\\)", r" \1 ", result)
        result = re.sub(r"\$\$\s*(.*?)\s*\$\$", r"\n\1\n", result, flags=re.DOTALL)
        result = re.sub(r"(?<!\$)\$(?!\$)(.*?)\$(?!\$)", r" \1 ", result)

        # 2. Balanced parsing for \frac{numerator}{denominator}
        while r"\frac" in result:
            pos = result.find(r"\frac")
            num, p2 = cls._extract_braced(result, pos + 5)
            if num is None:
                # Malformed \frac
                result = result[:pos] + result[pos + 5:]
                continue
            # Skip any whitespace between numerator and denominator
            while p2 < len(result) and result[p2].isspace():
                p2 += 1
            den, p3 = cls._extract_braced(result, p2)
            if den is None:
                result = result[:pos] + f"({num})" + result[p2:]
                continue

            # Format fraction
            clean_num = cls.format_math_text(num).strip()
            clean_den = cls.format_math_text(den).strip()
            if len(clean_num) <= 3 and len(clean_den) <= 3 and " " not in clean_num and " " not in clean_den:
                formatted_frac = f"{clean_num}/{clean_den}"
            else:
                formatted_frac = f"({clean_num} / {clean_den})"

            result = result[:pos] + formatted_frac + result[p3:]

        # 3. Balanced parsing for \sqrt
        while r"\sqrt" in result:
            pos = result.find(r"\sqrt")
            # Check optional [n]
            nth = None
            p2 = pos + 5
            if p2 < len(result) and result[p2] == '[':
                end_bracket = result.find(']', p2)
                if end_bracket != -1:
                    nth = result[p2 + 1:end_bracket].strip()
                    p2 = end_bracket + 1

            while p2 < len(result) and result[p2].isspace():
                p2 += 1

            content, p3 = cls._extract_braced(result, p2)
            if content is None:
                result = result[:pos] + "√" + result[p2:]
                continue

            clean_content = cls.format_math_text(content).strip()
            if nth:
                super_n = "".join(SUPERSCRIPTS.get(c, c) for c in nth)
                formatted_sqrt = f"{super_n}√({clean_content})"
            else:
                formatted_sqrt = f"√({clean_content})"

            result = result[:pos] + formatted_sqrt + result[p3:]

        # 4. Convert \text{...} to plain text
        result = re.sub(r"\\text\{([^{}]+)\}", r"\1", result)

        # 5. Remove \left, \right, \displaystyle
        result = re.sub(r"\\left|\\right|\\displaystyle", "", result)

        # 6. Replace known LaTeX symbol macros
        for macro, sym in LATEX_SYMBOLS.items():
            result = result.replace(macro, sym)

        # 7. Convert simple superscripts: x^{2} or x^2 -> x²
        def replace_super_bracket(match: re.Match) -> str:
            val = match.group(1)
            return "".join(SUPERSCRIPTS.get(c, c) for c in val)

        result = re.sub(r"\^\{([0-9nxy+-=()]+)\}", replace_super_bracket, result)

        def replace_super_single(match: re.Match) -> str:
            c = match.group(1)
            return SUPERSCRIPTS.get(c, f"^{c}")

        result = re.sub(r"\^([0-9nxy])", replace_super_single, result)

        # 8. Convert simple subscripts: x_{1} or x_1 -> x₁
        def replace_sub_bracket(match: re.Match) -> str:
            val = match.group(1)
            return "".join(SUBSCRIPTS.get(c, c) for c in val)

        result = re.sub(r"_\{([0-9aeoxij+-=()]+)\}", replace_sub_bracket, result)

        def replace_sub_single(match: re.Match) -> str:
            c = match.group(1)
            return SUBSCRIPTS.get(c, f"_{c}")

        result = re.sub(r"_([0-9aeoxij])", replace_sub_single, result)

        # 9. Clean remaining lone backslashes from common math keywords
        result = re.sub(r"\\(sin|cos|tan|log|ln|lim|exp)", r"\1", result)

        # 10. Clean up extra spaces around operators
        result = re.sub(r"[ ]{2,}", " ", result)

        return result


math_formatter = HumanMathFormatter()
