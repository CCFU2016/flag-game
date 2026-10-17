"""Judge a typed answer against a federation.

Accepts the poster name, World Rowing's name, the three-letter code and the
aliases in federations.py, ignoring filler words ("Republic of", "Islands"),
case, accents and small typos. A guess that names a *different* federation is
always wrong, so "Austria" never passes as a typo for "Australia".
"""
import re
import unicodedata
from difflib import SequenceMatcher

# Words that don't tell countries apart on their own.
GENERIC = set("""
the a an of and republic islands island state states federation kingdom st saint
""".split())


def ascii_fold(s):
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("ß", "ss").replace("æ", "ae").replace("Æ", "Ae").replace("ø", "o").replace("Ø", "O")
    return "".join(c for c in s if not unicodedata.combining(c))


def tokens(s):
    s = ascii_fold(s or "").lower()
    s = re.sub(r"\b((?:[a-z]\.){2,}[a-z]?)", lambda m: m.group(1).replace(".", ""), s)  # U.S.A. -> usa
    s = s.replace("&", " and ").replace("'", "").replace("’", "")
    return re.findall(r"[a-z0-9]+", s)


def core(toks):
    return [t for t in toks if t not in GENERIC]


def ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


def candidates(fed):
    """Every way of naming this federation that we accept."""
    names = (fed["name"], fed.get("wr_name"), fed["code"], *fed.get("aliases", []))
    return [t for t in (tokens(n) for n in names if n) if t]


def exact(guess, fed):
    """True when the guess is one of the federation's names (filler words aside)."""
    g = tokens(guess)
    gc = set(core(g))
    return bool(g) and any(g == c or (gc and gc == set(core(c))) for c in candidates(fed))


def judge(guess, fed, others=()):
    """'correct', 'close' or 'wrong' for a guess at `fed`; `others` are the
    federations a wrong-but-real country name should be checked against."""
    if exact(guess, fed):
        return "correct"
    if any(exact(guess, o) for o in others):
        return "wrong"  # they named another country
    g = tokens(guess)
    gc = core(g)
    if not gc:
        return "wrong"
    gc_join = " ".join(gc)
    best, close = 0.0, False
    for cand in candidates(fed):
        cc = core(cand)
        if not cc:
            continue
        cc_join = " ".join(cc)
        r = ratio(gc_join, cc_join)
        best = max(best, r)
        if r >= 0.85 and len(cc_join) >= 4:
            return "correct"  # small typo
        if set(gc) < set(cc) and any(len(t) >= 3 for t in gc):
            close = True  # part of a longer name ("Trinidad" alone is an alias, "Papua" is not)
    if close or best >= 0.7:
        return "close"
    return "wrong"


def pattern(name):
    """'New Zealand' -> 'N _ _   Z _ _ _ _ _ _   (3, 7)' : the crossword-style letter hint."""
    words = [w for w in re.split(r"\s+", name.strip()) if w]
    shapes, counts = [], []
    for w in words:
        letters = [c for c in w if c.isalnum()]
        if not letters:
            continue
        shapes.append(" ".join([letters[0]] + ["_"] * (len(letters) - 1)))
        counts.append(str(len(letters)))
    return "   ".join(shapes) + f"   ({', '.join(counts)})"
