"""Crawl oarspotter.com and build blades.db.

Only names, places, links and image URLs are stored. The blade images stay on
oarspotter.com (see README: they are Doug Rathburn's copyrighted work).

    uv run scrape.py            # uses cache/ for pages already fetched
    uv run scrape.py --refresh  # re-download every page
"""
import hashlib
import html
import json
import pathlib
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

from matching import tokens
from store import DB, SEED, export_seed, migrate

ROOT = pathlib.Path(__file__).parent
CACHE = ROOT / "cache"
HOME = "https://www.oarspotter.com/"
UA = "Mozilla/5.0 (blade-quiz; personal quiz, polite crawler)"

COUNTRY_NAMES = {
    "USA": "United States", "UK": "United Kingdom", "NewZealand": "New Zealand",
    "SouthAfrica": "South Africa", "HK": "Hong Kong", "Czech": "Czech Republic",
    "ElSalvador": "El Salvador", "PuertoRico": "Puerto Rico", "NatTeam": "National teams",
}
COLLEGE_PAGES = {
    "CambridgeUni": "Cambridge", "OxfordUni": "Oxford", "DurhamUni": "Durham",
    "LondonUni": "University of London", "HarvardUni": "Harvard",
}


def fetch(url, refresh=False):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".html")
    if path.exists() and not refresh:
        return path.read_text("latin-1")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=30).read()
    path.write_bytes(data)
    time.sleep(0.5)
    return data.decode("latin-1")


def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def crawl(refresh=False):
    """Return {url: html} for every blades page reachable from the home page."""
    queue, seen, pages = [], set(), {}
    for href in re.findall(r'href="([^"#]+\.html?)"', fetch(HOME, refresh), re.I):
        url = urllib.parse.urljoin(HOME, href).replace("http://", "https://")
        if url.startswith(HOME + "blades/") and url not in seen:
            seen.add(url)
            queue.append(url)
    while queue:
        url = queue.pop(0)
        try:
            page = fetch(url, refresh)
        except Exception as exc:  # a dead link shouldn't stop the crawl
            print("  skip", url, exc)
            continue
        pages[url] = page
        for href in re.findall(r'href="([^"#]+\.html?)"', page, re.I):
            nxt = urllib.parse.urljoin(url, href).replace("http://", "https://")
            if nxt.startswith(HOME + "blades/") and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return pages


def page_meta(url):
    parts = urllib.parse.urlparse(url).path.split("/")  # ['', 'blades', 'USA', 'Uni', 'USA_Uni.html']
    key = parts[2]
    stem = parts[-1].rsplit(".", 1)[0]
    country = COUNTRY_NAMES.get(key, key)
    if key == "NatTeam":
        return country, "National teams", None
    if stem in COLLEGE_PAGES:
        return country, "Colleges", COLLEGE_PAGES[stem]
    if stem.endswith("_Uni"):
        return country, "Universities", None
    if stem.endswith("_HS"):
        return country, "Schools & juniors", None
    if stem.endswith("_Indoor"):
        return country, "Indoor & health clubs", None
    if stem.endswith("_Province"):
        return country, "Associations", None
    return country, "Clubs", None


def section_category(heading, default):
    h = heading.lower()
    if "student" in h or "universit" in h:
        return "Universities"
    if "school" in h or "junior" in h:
        return "Schools & juniors"
    if "club" in h:
        return "Clubs"
    return default


def parse(url, page):
    country, category, college_of = page_meta(url)
    headings = [(m.start(), text(m.group(1))) for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", page, re.S | re.I)]
    sub_headings = headings[1:] if len(headings) > 1 else []  # first h2 is the page title
    rows = []
    for m in re.finditer(r'<td class="list">(.*?)</td>', page, re.S | re.I):
        cell = m.group(1)
        img = re.search(r'<img\b[^>]*\bsrc="([^"]+)"[^>]*>', cell, re.I)
        bold = re.search(r"<b>(.*?)</b>", cell, re.S | re.I)
        if not img or not bold:
            continue
        name = text(bold.group(1))
        alt = re.search(r'\balt="([^"]*)"', img.group(0), re.I)
        short = text(alt.group(1)) if alt else ""
        loc = re.search(r"<i>\s*-?\s*(.*?)</i>", cell, re.S | re.I)
        location = text(loc.group(1)) if loc else ""
        link = re.search(r'<a\b[^>]*href="(https?://[^"]+)"', cell, re.I)

        code = ""
        if category == "National teams":
            m_code = re.search(r"\s*-\s*([A-Z]{3})$", name)  # "Afghanistan - AFG", "Saudi Arabia- KSA"
            if m_code:
                name, code = name[: m_code.start()].strip(), m_code.group(1)
        name = re.sub(r"\s*-\s*(Men|Women|Men's|Women's|Lightweight).*$", "", name, flags=re.I).strip(" ,-")
        if not name:
            continue

        cat, section = category, None
        before = [h for pos, h in sub_headings if pos < m.start()]
        if before:
            section = before[-1].rstrip(":")
            cat = section_category(section, category)
        if college_of:
            section = f"{college_of} colleges"
            location = location or college_of

        image_url = urllib.parse.urljoin(url, img.group(1)).replace("http://", "https://")
        rows.append(dict(
            name=name, short=short, code=code, location=location, country=country,
            category=cat, section=section, image_url=image_url,
            club_url=link.group(1) if link else "", source_url=url,
            solid=int("/Solid/" in image_url),
        ))
    return rows




WORLD_ROWING = "https://world-rowing-api.soticcloud.net/stats/api/country/"


def world_rowing_countries(refresh=False):
    """World Rowing's own country list: [{CountryCode, DisplayName, IsFormerCountry}, ...]."""
    path = CACHE / "worldrowing_countries.json"
    if refresh or not path.exists():
        req = urllib.request.Request(WORLD_ROWING, headers={"User-Agent": UA})
        path.write_bytes(urllib.request.urlopen(req, timeout=30).read())
    return json.loads(path.read_text())["data"]


def add_world_rowing(rows, refresh=False):
    """Give each national team World Rowing's code and name. OarSpotter has some
    older codes (ROM, VNE, MLD) and names (Swaziland, Turkey)."""
    countries = sorted(world_rowing_countries(refresh), key=lambda c: bool(c["IsFormerCountry"]))
    by_name, by_code = {}, {}
    for c in countries:
        by_name.setdefault(frozenset(tokens(c["DisplayName"])), c)
        by_code.setdefault(c["CountryCode"], c)
    for r in rows:
        if r["category"] != "National teams":
            continue
        c = by_name.get(frozenset(tokens(r["name"]))) or by_code.get(r["code"])
        r["wr_code"], r["wr_name"] = (c["CountryCode"], c["DisplayName"]) if c else ("", "")


def main():
    refresh = "--refresh" in sys.argv
    pages = crawl(refresh)
    rows = [r for url, page in pages.items() for r in parse(url, page)]
    for r in rows:
        r.setdefault("wr_code", "")
        r.setdefault("wr_name", "")
    add_world_rowing(rows, refresh)
    con = sqlite3.connect(DB)
    migrate(con)
    # The old parser stored "Saudi Arabia- KSA" as a name; drop it unless it has answers.
    con.execute("""DELETE FROM blades WHERE name LIKE '%- ___' AND category = 'National teams'
                   AND id NOT IN (SELECT blade_id FROM answers)""")
    # Upsert keeps blade ids stable across re-scrapes, so answer history survives.
    con.executemany(
        """INSERT INTO blades (name, short, code, location, country, category, section,
                               image_url, club_url, source_url, solid, wr_code, wr_name)
           VALUES (:name, :short, :code, :location, :country, :category, :section,
                   :image_url, :club_url, :source_url, :solid, :wr_code, :wr_name)
           ON CONFLICT (name, image_url) DO UPDATE SET
               short=excluded.short, code=excluded.code, location=excluded.location,
               club_url=excluded.club_url, wr_code=excluded.wr_code, wr_name=excluded.wr_name""",
        rows,
    )
    con.commit()
    export_seed(con)
    total, solid = con.execute("SELECT count(*), sum(solid) FROM blades").fetchone()
    print(f"{len(pages)} pages, {len(rows)} rows -> {total} blades in {DB.name} and {SEED.relative_to(ROOT)} ({solid} plain one-colour)")


if __name__ == "__main__":
    main()
