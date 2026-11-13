import sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = r"c:\Users\monsm\Downloads\New folder (6)\New folder"

# 1. timezone: normalise map keys once at import
P = ROOT + r"\utils\timezone_resolver.py"
s = open(P, encoding='utf-8').read()
OLD = '''def resolve_timezone(location: str) -> Tuple[str, str, str]:'''
NEW = '''# Normalise all keys once so 'السعودية' / 'القاهرة' (ة) match normalised input ('ه')
_TZ_MAP = {_normalise(k): v for k, v in _TZ_MAP.items()}


def resolve_timezone(location: str) -> Tuple[str, str, str]:'''
if "_TZ_MAP = {_normalise(k)" not in s:
    s = s.replace(OLD, NEW, 1)
    open(P, 'w', encoding='utf-8').write(s)
    print("✅ timezone keys normalised")

# 2. creator insult window: 2 words before name, 2 words after name end
P = ROOT + r"\bot_factory\sibling_bot_network.py"
s = open(P, encoding='utf-8', newline='').read()
nl = "\r\n" if "\r\n" in s else "\n"
OLD = '''        words = self._norm(entry.message_text).split()
        joined_positions = []
        for i in range(len(words)):
            window2 = " ".join(words[i:i + 2])
            if any(self._norm(t) in (words[i], window2) for t in self.CREATOR_TOKENS):
                joined_positions.append(i)
        if not joined_positions:
            return False
        for pos in joined_positions:
            window = " ".join(words[max(0, pos - 4): pos + 6])
            if any(re.search(p, window) for p in self.DISRESPECT_PATTERNS):
                return True
        return False'''.replace("\n", nl)
NEW = '''        words = self._norm(entry.message_text).split()
        spans = []  # (start_idx, end_idx) of each creator-name occurrence
        for i in range(len(words)):
            window2 = " ".join(words[i:i + 2])
            for t in self.CREATOR_TOKENS:
                tn = self._norm(t)
                if tn == window2 and " " in tn:
                    spans.append((i, i + 1))
                elif tn == words[i]:
                    spans.append((i, i))
        if not spans:
            return False
        for start, end in spans:
            # Insult must be directly attached: up to 2 words before the name or 2 words after it
            window = " ".join(words[max(0, start - 2): start] + words[end + 1: end + 3])
            if any(re.search(p, window) for p in self.DISRESPECT_PATTERNS):
                return True
        return False'''.replace("\n", nl)
if OLD in s:
    s = s.replace(OLD, NEW, 1)
    open(P, 'w', encoding='utf-8', newline='').write(s)
    print("✅ creator insult window tightened")
else:
    print("⚠️ creator window anchor missing")

