"""Blade Quiz: see a national federation's blade, name the country.

    uv run app.py   ->  http://127.0.0.1:5040
    On Railway: gunicorn (see railway.toml), listening on $PORT.
"""
import os
import random
import sqlite3
import sys

from flask import Flask, abort, g, jsonify, render_template, request, send_file

from federations import load
from matching import judge, pattern
from store import DB, ensure_db

PORT = 5040

FEDS = load()
BY_ID = {f["id"]: f for f in FEDS}
CONTINENTS = sorted({f["continent"] for f in FEDS})

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


def fed(fed_id):
    f = BY_ID.get(fed_id)
    if f is None:
        abort(404)
    return f


def public(f):
    """What the browser may see once a question is over."""
    wr_name = f["wr_name"] if f["wr_name"].lower() != f["name"].lower() else ""
    return dict(id=f["id"], name=f["name"], code=f["code"], wr_name=wr_name, continent=f["continent"])


def last_results():
    """{code: 1/0} for the most recent answer per federation."""
    rows = db().execute(
        "SELECT code, correct FROM answers a WHERE a.id = (SELECT max(id) FROM answers WHERE code = a.code)"
    ).fetchall()
    return {r["code"]: r["correct"] for r in rows}


def pool(args):
    continents = [c for c in args.get("continents", "").split("|") if c]
    feds = [f for f in FEDS if not continents or f["continent"] in continents]
    mode = args.get("mode", "all")
    if mode in ("unseen", "misses"):
        last = last_results()
        if mode == "unseen":
            feds = [f for f in feds if f["code"] not in last]
        else:
            feds = [f for f in feds if last.get(f["code"]) == 0]  # last attempt was "Show me"
    return feds


def stats_dict():
    last = last_results()
    known = sum(last.values())
    return dict(total=len(FEDS), seen=len(last), known=known, misses=len(last) - known)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/meta")
def meta():
    counts = [dict(continent=c, n=sum(f["continent"] == c for f in FEDS)) for c in CONTINENTS]
    return jsonify(continents=counts, stats=stats_dict())


@app.get("/api/pool")
def pool_size():
    return jsonify(pool=len(pool(request.args)))


@app.get("/api/question")
def question():
    def id_list(name):
        return {int(x) for x in request.args.get(name, "").split(",") if x.isdigit()}

    ids = [f["id"] for f in pool(request.args)]
    in_round = id_list("round")
    if not ids:
        if in_round:  # e.g. every miss has now been answered
            return jsonify(done=True, pool=0)
        return jsonify(error="No blades match these settings."), 404
    # Prefer blades not shown this session; never repeat one within a round.
    options = [i for i in ids if i not in id_list("exclude")] or [i for i in ids if i not in in_round]
    if not options:
        return jsonify(done=True, pool=len(ids))
    f = BY_ID[random.choice(options)]
    return jsonify(id=f["id"], img=f"/img/{f['id']}", continent=f["continent"], pool=len(ids))


@app.get("/img/<int:fed_id>")
def image(fed_id):
    # Served by id so the file name (the country code) doesn't give the answer away.
    return send_file(fed(fed_id)["image"], mimetype="image/png", max_age=86400)


@app.get("/api/hint/<int:fed_id>/<int:level>")
def hint(fed_id, level):
    f = fed(fed_id)
    hints = {
        1: ("Code", pattern(f["code"])),
        2: ("Letters", pattern(f["name"])),
        3: ("Code", f["code"]),
    }
    if level not in hints:
        abort(404)
    label, text = hints[level]
    return jsonify(label=label, text=text)


def record(f, correct, body):
    db().execute(
        "INSERT INTO answers (code, correct, hints, tries, last_guess) VALUES (?, ?, ?, ?, ?)",
        (f["code"], int(correct), int(body.get("hints", 0)), int(body.get("tries", 1)), body.get("guess", "")[:200]),
    )
    db().commit()


@app.post("/api/answer")
def answer():
    body = request.get_json(force=True)
    f = fed(int(body["id"]))
    result = judge(body.get("guess", ""), f, [o for o in FEDS if o is not f])
    if result == "correct":
        record(f, True, body)
        return jsonify(result=result, blade=public(f))
    return jsonify(result=result)


@app.post("/api/reveal")
def reveal():
    body = request.get_json(force=True)
    f = fed(int(body["id"]))
    record(f, False, body)
    return jsonify(blade=public(f))


@app.get("/api/stats")
def stats():
    return jsonify(stats_dict())


if __name__ == "__main__":
    host = "0.0.0.0" if "--lan" in sys.argv or "PORT" in os.environ else "127.0.0.1"
    app.run(host=host, port=int(os.environ.get("PORT", PORT)), debug="--debug" in sys.argv)
