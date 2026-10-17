"""Cut every blade out of World Rowing's member-federations poster.

    uv run extract_pdf.py "158-Member-Federations-A4-landscape-5.8.26.pdf"

Writes data/blades/<CODE>.png (one per federation) and data/federations.json
(code, name as printed, position on the poster). The poster is a single page:
a 12 x 14 grid, each blade drawn above a "NAME  CODE" label.
"""
import json
import pathlib
import re
import sys
import urllib.request

import pymupdf
from PIL import Image

ROOT = pathlib.Path(__file__).parent
OUT_DIR = ROOT / "data" / "blades"
OUT_JSON = ROOT / "data" / "federations.json"

WORLD_ROWING = "https://world-rowing-api.soticcloud.net/stats/api/country/"
SMALL_WORDS = {"of", "and", "the"}

ROW_PITCH = 32.0   # points between label rows
COL_WIDTH = 58.0   # points between columns
ZOOM = 10          # render scale: 1 pt -> 10 px


def label_spans(page):
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for s in line["spans"]:
                t = s["text"].strip()
                if t and s["size"] < 5:  # labels are tiny; skips the title
                    x0, y0, x1, y1 = s["bbox"]
                    spans.append(dict(x0=x0, y0=y0, x1=x1, y1=y1, t=t))
    return spans


def cells(spans):
    """Group label spans by grid cell: {(row, col): [spans]}."""
    first_col = min(s["x0"] for s in spans)
    first_row = min(s["y0"] for s in spans)
    grid = {}
    for s in spans:
        col = int((s["x0"] - first_col + 3) // COL_WIDTH)
        row = round((s["y0"] - first_row) / ROW_PITCH)
        grid.setdefault((row, col), []).append(s)
    col_starts = [first_col + i * COL_WIDTH for i in range(max(c for _, c in grid) + 1)]
    return grid, col_starts


def parse_label(group):
    """'AMERICAN' 'ASA' / 'SAMOA'  ->  ('ASA', 'AMERICAN SAMOA')."""
    group = sorted(group, key=lambda s: (round(s["y0"]), s["x0"]))
    words, code = [], None
    for s in group:
        m = re.fullmatch(r"(.*?)\s*\b([A-Z]{3})", s["t"])
        if code is None and m and (s["t"] == m.group(2) or s["x1"] - s["x0"] > 30):
            if m.group(1):
                words.append(m.group(1))
            code = m.group(2)
        else:
            words.append(s["t"])
    name = re.sub(r"\s+", " ", " ".join(words)).replace("- ", "-").strip()
    return code, name


def nice_name(poster_name):
    """'PEOPLE’S REPUBLIC OF CHINA' -> 'People’s Republic of China', keeps 'DPR'."""
    words = []
    for i, w in enumerate(poster_name.split()):
        if w in ("DPR", "&"):
            words.append(w)
        elif i and w.lower() in SMALL_WORDS:
            words.append(w.lower())
        else:
            words.append("-".join(p[:1] + p[1:].lower() for p in w.split("-")))
    return " ".join(words)


def world_rowing_names():
    """World Rowing's own name per code, e.g. CIV -> 'Ivory Coast', CZE -> 'Czechia'."""
    req = urllib.request.Request(WORLD_ROWING, headers={"User-Agent": "Mozilla/5.0 (blade-quiz)"})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())["data"]
    return {c["CountryCode"]: c["DisplayName"] for c in data if not c["IsFormerCountry"]}


def crop_to_ink(png_path):
    """Trim the transparent/white margin around a rendered blade."""
    im = Image.open(png_path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 0))
    # Treat near-white as background too, then crop with a small margin.
    px = im.load()
    w, h = im.size
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 20 and not (r > 245 and g > 245 and b > 245):
                xs.append(x)
                ys.append(y)
    if not xs:
        return
    m = 4
    box = (max(min(xs) - m, 0), max(min(ys) - m, 0), min(max(xs) + m + 1, w), min(max(ys) + m + 1, h))
    im.crop(box).save(png_path, optimize=True)
    del bg


def main(pdf_path):
    page = pymupdf.open(pdf_path)[0]
    grid, col_starts = cells(label_spans(page))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    feds = []
    for (row, col), group in sorted(grid.items()):
        code, name = parse_label(group)
        if not code:
            print("  no code in cell", row, col, [s["t"] for s in group])
            continue
        top = min(s["y0"] for s in group)
        # Start below the label of the cell above (some labels run to two lines).
        above = grid.get((row - 1, col), [])
        ceiling = max([s["y1"] for s in above], default=top - ROW_PITCH + 5) + 0.3
        x0 = col_starts[col] - 3
        clip = pymupdf.Rect(x0, max(ceiling, top - ROW_PITCH + 5), x0 + COL_WIDTH - 1, top - 0.6)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), clip=clip, alpha=True)
        path = OUT_DIR / f"{code}.png"
        pix.save(path)
        crop_to_ink(path)
        feds.append(dict(code=code, name=nice_name(name), poster_name=name, row=row, col=col))
    wr = world_rowing_names()
    for f in feds:
        f["wr_name"] = wr.get(f["code"], "")
        if not f["wr_name"]:
            print("  not in World Rowing's country list:", f["code"], f["name"])
    OUT_JSON.write_text(json.dumps(feds, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(feds)} federations -> {OUT_JSON.relative_to(ROOT)} and {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main(sys.argv[1])
