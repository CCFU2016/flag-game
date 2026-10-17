# Blade Quiz

See a national team's rowing blade, type the country. All 158 World Rowing
member federations, cut from World Rowing's *158 Member Federations* poster
(August 2026).

```bash
uv run app.py          # http://127.0.0.1:5040
uv run app.py --lan    # reachable from your phone on the same wifi
```

## How it plays

- **Open answers.** No multiple choice. The country name, World Rowing's name
  for it ("Czechia", "Ivory Coast") and its three-letter code ("NED") all count,
  as do common names ("Holland", "UK", "Taiwan") and small typos.
- **Naming a different country is always wrong**, even when it's one letter
  off ("Austria" for Australia, "Dominica" for Dominican Republic). Half a name
  ("Papua") gets "Close" and a free retry.
- The continent is shown with every blade, for free.
- **Hints**, one at a time: the code's first letter (`N _ _`), then the letters
  of the name crossword-style (`N _ _ _ _ _ _ _ _ _ _ (11)`), then the code.
- **Scoring**: 3 for a clean answer, minus 1 per hint or wrong guess, at least 1
  if you get there, 0 for "Show me".
- **Filters**: continents, and *All / Not seen yet / My misses*. "My misses" is
  every blade whose last attempt ended in "Show me".

## Data

- `data/blades/<CODE>.png` and `data/federations.json` come from the poster:

  ```bash
  uv run extract_pdf.py "158-Member-Federations-A4-landscape-5.8.26.pdf"
  ```

  It reads the label under each blade (name and code), renders the blade at
  10x and trims it, and adds World Rowing's own name per code from its
  country API. Re-run it when a new poster comes out.
- `federations.py` holds what the poster doesn't: continents and extra
  accepted names. Add aliases there.
- `quiz.db` (not committed) holds your answers.

## Deploy (Railway)

Railway deploys from GitHub on push (`Procfile`: gunicorn on `$PORT`; the
service has `PORT=5040` to match its domain). Answers live in the container's
SQLite file, so they reset on every deploy and are shared by everyone using
the link.

## Files

- `extract_pdf.py`: poster -> blade images and names
- `federations.py`: loads the data, continents, aliases
- `matching.py`: how a typed answer is judged
- `app.py`: Flask app and API; `store.py`: answer history
- `templates/`, `static/`: the single-page front end
