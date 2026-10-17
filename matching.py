"""Judge a typed answer against a club name.

People never type "Koninklijke Studenten Roeivereniging Njord"; they type
"njord". So we compare on the distinctive words of the name (club/rowing/boat
and friends stripped), allow small typos, and accept the site's short name.
"""
import re
import unicodedata
from difflib import SequenceMatcher

# Words that say "this is a rowing organisation" rather than which one.
GENERIC = set("""
the a an of and at on in for de het t van der den die das des du la le les el los las l d
rowing row rowers crew crews club clubs boat boats boating bc rc brc rfc rowingclub boatclub
association assoc society team teams program programme academy foundation inc ltd republic
university uni universitat universite universidad universita college school schools high hs
junior juniors scholastic community masters alumni men women mens womens lightweights
roeivereniging roeien roei rv zeilvereniging zeilvereeniging roeivereeniging watersport watersportvereniging
vereniging vereeniging studenten koninklijke ksrv asrv dsrv
ruderclub ruder rudern ruderverein rudergesellschaft ruderverband rudergemeinschaft rv rg rc ev e v verein club
aviron nautique societe sportive sport sports cercle as sn
remo club clube canottieri societa canottaggio sc
roklubb roklub roddklubb roddarklubb
""".split())


def ascii_fold(s):
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("ß", "ss").replace("æ", "ae").replace("Æ", "Ae").replace("ø", "o").replace("Ø", "O")
    return "".join(c for c in s if not unicodedata.combining(c))


def tokens(s):
    s = ascii_fold(s or "").lower()
    s = re.sub(r"\b((?:[a-z]\.){2,}[a-z]?)", lambda m: m.group(1).replace(".", ""), s)  # K.S.R.V. -> ksrv
    s = s.replace("&", " and ").replace("'", "").replace("’", "")
    s = re.sub(r"\(.*?\)", " ", s) + " " + " ".join(re.findall(r"\((.*?)\)", s))
    return re.findall(r"[a-z0-9]+", s)


def core(toks):
    return [t for t in toks if t not in GENERIC]


def ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


NICKNAMES = {
    "Netherlands": ["Holland"], "Great Britain": ["GB", "Britain", "UK"],
    "United States of America": ["United States", "US", "America"], "Germany": ["Deutschland"],
}


def candidates(blade):
    """Every way of naming this blade that we accept."""
    out = []
    extra = NICKNAMES.get(blade["name"], []) if blade.get("category") == "National teams" else []
    # National teams: OarSpotter's code plus World Rowing's current code and name (ROU, Czechia, ...).
    for raw in (blade["name"], blade.get("short"), blade.get("code"), blade.get("wr_code"), blade.get("wr_name"), *extra):
        if raw:
            out.append(tokens(raw))
    # "Balliol College" on the Oxford page: "Balliol Oxford" is a fine answer too.
    if blade.get("section") and blade["section"].endswith("colleges"):
        out.append(tokens(blade["name"]) + tokens(blade["section"].replace(" colleges", "")))
    return [c for c in out if c]


def judge(guess, blades):
    """Return 'correct', 'close' or 'wrong' for a guess against one or more blades
    (several clubs can share one design; naming any of them counts)."""
    g = tokens(guess)
    if not g:
        return "wrong"
    gc = core(g)
    g_join, gc_join = " ".join(g), " ".join(gc)
    best = 0.0
    close = False
    for blade in blades:
        place = set(tokens(" ".join(filter(None, [blade.get("location"), blade.get("country"), blade.get("section")]))))
        for cand in candidates(blade):
            cc = core(cand)
            c_join, cc_join = " ".join(cand), " ".join(cc)
            if g_join == c_join or (gc and set(gc) == set(cc)):
                return "correct"
            if gc and cc:
                r = ratio(gc_join, cc_join)
                best = max(best, r)
                if r >= 0.85 and len(cc_join) >= 4:
                    return "correct"  # small typo
                # They added the town ("Leander Henley"); other extra words could name another club.
                if set(cc) < set(gc) and set(gc) - set(cc) <= place:
                    return "correct"
                # They typed part of a multi-word name ("Oxford" for "Oxford Brookes").
                if set(gc) < set(cc) and any(len(t) >= 3 for t in gc):
                    close = True
                # Typo inside one word of a longer guess or name.
                for gt in gc:
                    for ct in cc:
                        if len(ct) >= 5 and ratio(gt, ct) >= 0.85 and len(cc) == 1:
                            return "correct"
            elif not cc and ratio(g_join, c_join) >= 0.85:
                return "correct"  # name was all generic words, e.g. "Rowing Club"
    if close or best >= 0.7:
        return "close"
    return "wrong"


def pattern(name):
    """'De Hoop' -> 'D _   H _ _ _   (2, 4)' : the crossword-style letter hint."""
    words = [w for w in re.split(r"\s+", name.strip()) if w]
    shapes, counts = [], []
    for w in words:
        letters = [c for c in w if c.isalnum()]
        if not letters:
            continue
        shapes.append(" ".join([letters[0]] + ["_"] * (len(letters) - 1)))
        counts.append(str(len(letters)))
    return "   ".join(shapes) + f"   ({', '.join(counts)})"
