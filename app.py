"""Blade Quiz: see a rowing blade, name the club.

    uv run app.py   ->  http://127.0.0.1:5040
    On Railway: gunicorn (see railway.toml), listening on $PORT.
"""
import os
import random
import sqlite3
import sys
import urllib.request
from collections import OrderedDict

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request

from matching import judge, pattern, tokens
from store import DB, ensure_db

PORT = 5040
# Locally the images are fetched through this app, which hides the file name (often
# the club's name). On a public deploy we don't copy OarSpotter's images: the
# browser loads them straight from oarspotter.com.
PROXY_IMAGES = not os.environ.get("RAILWAY_ENVIRONMENT")

app = Flask(__name__)
ensure_db()


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    if (con := g.pop("db", None)) is not None:
        con.close()


def blade(blade_id):
    row = db().execute("SELECT * FROM blades WHERE id = ?", (blade_id,)).fetchone()
    if row is None:
        abort(404)
    return dict(row)


def same_design(b):
    """Other clubs that use exactly the same blade image."""
    rows = db().execute(
        "SELECT * FROM blades WHERE image_url = ? AND id != ? ORDER BY name", (b["image_url"], b["id"])
    ).fetchall()
    return [dict(r) for r in rows]


def public(b):
    """What the browser may see once a question is over."""
    keys = ("id", "name", "short", "code", "location", "country", "category", "section", "club_url", "source_url", "solid")
    out = {k: b[k] for k in keys}
    out["code"] = b["wr_code"] or b["code"]  # show World Rowing's code where it has one
    out["wr_code"] = b["wr_code"]
    out["wr_name"] = b["wr_name"] if b["wr_name"] and set(tokens(b["wr_name"])) != set(tokens(b["name"])) else ""
    others = same_design(b)
    out["shared_with"] = [] if b["solid"] else [o["name"] for o in others[:6]]
    return out


def filters(args):
    where, params = [], []
    countries = [c for c in args.get("countries", "").split("|") if c]
    categories = [c for c in args.get("categories", "").split("|") if c]
    if countries:
        where.append(f"country IN ({','.join('?' * len(countries))})")
        params += countries
    if categories:
        where.append(f"category IN ({','.join('?' * len(categories))})")
        params += categories
    if args.get("solid") != "1":
        where.append("solid = 0")
    mode = args.get("mode", "all")
    if mode == "unseen":
        where.append("id NOT IN (SELECT blade_id FROM answers)")
    elif mode == "misses":
        # Last attempt at this blade was a give-up.
        where.append("""id IN (SELECT blade_id FROM answers a
                               WHERE a.id = (SELECT max(id) FROM answers WHERE blade_id = a.blade_id)
                                 AND a.correct = 0)""")
    return " AND ".join(where) or "1", params


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/meta")
def meta():
    con = db()
    countries = con.execute(
        "SELECT country, count(*) n FROM blades WHERE solid = 0 GROUP BY country ORDER BY n DESC, country"
    ).fetchall()
    categories = con.execute(
        "SELECT category, count(*) n FROM blades WHERE solid = 0 GROUP BY category ORDER BY n DESC"
    ).fetchall()
    return jsonify(
        countries=[dict(r) for r in countries],
        categories=[dict(r) for r in categories],
        stats=stats_dict(),
    )


def stats_dict():
    con = db()
    total = con.execute("SELECT count(*) FROM blades WHERE solid = 0").fetchone()[0]
    seen, right = con.execute(
        """SELECT count(*), coalesce(sum(correct), 0) FROM answers a
           WHERE a.id = (SELECT max(id) FROM answers WHERE blade_id = a.blade_id)"""
    ).fetchone()
    return dict(total=total, seen=seen, known=right, misses=seen - right)


@app.get("/api/pool")
def pool():
    where, params = filters(request.args)
    n = db().execute(f"SELECT count(*) FROM blades WHERE {where}", params).fetchone()[0]
    return jsonify(pool=n)


@app.get("/api/question")
def question():
    where, params = filters(request.args)
    def id_list(name):
        return {int(x) for x in request.args.get(name, "").split(",") if x.isdigit()}

    ids = [r[0] for r in db().execute(f"SELECT id FROM blades WHERE {where}", params)]
    in_round = id_list("round")
    if not ids:
        if in_round:  # e.g. every miss has now been answered
            return jsonify(done=True, pool=0)
        return jsonify(error="No blades match these settings."), 404
    # Prefer blades not shown this session; never repeat one within a round.
    options = [i for i in ids if i not in id_list("exclude")] or [i for i in ids if i not in in_round]
    if not options:
        return jsonify(done=True, pool=len(ids))
    blade_id = random.choice(options)
    return jsonify(id=blade_id, img=f"/img/{blade_id}", country=blade(blade_id)["country"], pool=len(ids))


_img_cache = OrderedDict()


@app.get("/img/<int:blade_id>")
def image(blade_id):
    # Proxied so the file name (often the club name) doesn't give the answer away.
    # Held in memory only; the images belong to OarSpotter.com.
    if not PROXY_IMAGES:
        return redirect(blade(blade_id)["image_url"])
    if blade_id not in _img_cache:
        url = blade(blade_id)["image_url"]
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.oarspotter.com/"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                _img_cache[blade_id] = (resp.read(), resp.headers.get_content_type())
        except Exception:
            abort(502)
        if len(_img_cache) > 400:
            _img_cache.popitem(last=False)
    data, ctype = _img_cache[blade_id]
    return Response(data, mimetype=ctype, headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/hint/<int:blade_id>/<int:level>")
def hint(blade_id, level):
    b = blade(blade_id)
    code = b["wr_code"] or b["code"]
    if b["category"] == "National teams" and code:
        # No town or kind to give away here: build up to the World Rowing code instead.
        hints = {
            1: ("Code", pattern(code)),
            2: ("Letters", pattern(b["name"])),
            3: ("Code", code),
        }
        if level not in hints:
            abort(404)
        label, text = hints[level]
        return jsonify(label=label, text=text)
    if level == 1:  # the country is already on screen
        return jsonify(label="Kind", text=b["section"] or b["category"])
    if level == 2:
        return jsonify(label="Town", text=b["location"] or "No town listed for this one")
    if level == 3:
        return jsonify(label="Letters", text=pattern(b["short"] or b["name"]))
    abort(404)


def record(blade_id, correct, body):
    db().execute(
        "INSERT INTO answers (blade_id, correct, hints, tries, last_guess) VALUES (?, ?, ?, ?, ?)",
        (blade_id, int(correct), int(body.get("hints", 0)), int(body.get("tries", 1)), body.get("guess", "")[:200]),
    )
    db().commit()


@app.post("/api/answer")
def answer():
    body = request.get_json(force=True)
    b = blade(int(body["id"]))
    accepted = [b] + same_design(b)
    result = judge(body.get("guess", ""), accepted)
    if result == "correct":
        record(b["id"], True, body)
        return jsonify(result=result, blade=public(b))
    return jsonify(result=result)


@app.post("/api/reveal")
def reveal():
    body = request.get_json(force=True)
    b = blade(int(body["id"]))
    record(b["id"], False, body)
    return jsonify(blade=public(b))


@app.get("/api/stats")
def stats():
    return jsonify(stats_dict())


if __name__ == "__main__":
    host = "0.0.0.0" if "--lan" in sys.argv or "PORT" in os.environ else "127.0.0.1"
    app.run(host=host, port=int(os.environ.get("PORT", PORT)), debug="--debug" in sys.argv)
