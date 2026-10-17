# Blade Quiz

See a rowing oar, type the club it belongs to. ~4,000 blades from
[OarSpotter.com](https://www.oarspotter.com/): clubs, universities, schools,
Oxbridge colleges and national teams, 55 countries.

```bash
uv run app.py          # http://127.0.0.1:5040
uv run app.py --lan    # reachable from your phone on the same wifi
```

## How it plays

- **Open answers.** No multiple choice. Short names count ("Njord", "Leander",
  "DDS"), as do small typos, any word order, and adding the town ("Leander Henley").
  A half-right answer ("Oxford" for Oxford Brookes) gets "Close" and a free retry.
- **National teams** take the country name or its World Rowing code (NED, ROU,
  KSA). Both OarSpotter's older codes and names (ROM, Swaziland) and World Rowing's
  current ones (ROU, Eswatini, Czechia, Türkiye) count. `scrape.py` pulls the codes
  from World Rowing's country list.
- **The country is shown** with every blade, for free.
- **Hints**, one at a time: kind of crew, then town, then the letters
  crossword-style (`H _ _ _ _ _ _ _ _ (9)`).
- **Scoring**: 3 for a clean answer, minus 1 per hint or wrong guess, at least 1
  if you get there, 0 for "Show me".
- **Filters**: countries, kind of crew, and *All / Not seen yet / My misses*.
  "My misses" is every blade whose last attempt ended in "Show me".
- Plain one-colour blades (232 of them, many shared) are off by default. When on,
  naming any club with that colour counts. The same goes for the ~70 designs
  that several clubs share.

## Data

`uv run scrape.py` crawls the site (pages cached in `cache/`, half a second
between requests), fills `blades.db` and writes `data/blades.json`. Re-run with
`--refresh` to pick up new blades; your answer history is kept.

`data/blades.json` is committed; `blades.db` (your answers) is not. On start the
app builds or updates `blades.db` from the JSON, so a fresh checkout works
without crawling.

## Deploy (Railway)

Railway deploys from GitHub on push (`railway.toml`: gunicorn on `$PORT`). There
the images are not proxied: `/img/<id>` redirects to oarspotter.com. Answers
live in the container's SQLite file, so they reset on every deploy and are
shared by everyone using the link.

Only names, towns, links and image URLs are stored. The images are fetched
from oarspotter.com when shown and are not saved: they are Doug Rathburn's
copyrighted work ("may not be reproduced by any means without permission").
Fine for playing at home; ask him (doug@rathburn.net) before putting this
online or sharing it.

## Files

- `scrape.py`: crawler and parser
- `matching.py`: how a typed answer is judged
- `app.py`: Flask app and API
- `templates/`, `static/`: the single-page front end
