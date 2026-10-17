const $ = (id) => document.getElementById(id);
const KEY = "blade-quiz-federations";

const defaults = { continents: [], mode: "all", length: 10 };
let settings = { ...defaults };
try { settings = { ...defaults, ...JSON.parse(localStorage.getItem(KEY) || "{}") }; } catch {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch {} };

let round, current, seen = [];

function query(extra = {}) {
  const p = new URLSearchParams({
    continents: settings.continents.join("|"),
    mode: settings.mode,
    ...extra,
  });
  return p.toString();
}

async function api(path, body) {
  const res = await fetch(path, body ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  } : undefined);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function show(screen) {
  for (const id of ["setup", "quiz", "summary"]) $(id).hidden = id !== screen;
  window.scrollTo(0, 0);
}

/* ---------- Setup ---------- */

function chip(label, n, pressed, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "chip";
  b.setAttribute("aria-pressed", pressed);
  b.textContent = label;
  if (n != null) {
    const s = document.createElement("span");
    s.className = "n";
    s.textContent = n.toLocaleString();
    b.append(s);
  }
  b.onclick = onClick;
  return b;
}

function renderChips(el, items, key, labelKey, allLabel) {
  el.replaceChildren();
  const chosen = settings[key];
  el.append(chip(allLabel, null, chosen.length === 0, () => { settings[key] = []; changed(); }));
  for (const it of items) {
    const v = it[labelKey];
    el.append(chip(v, it.n, chosen.includes(v), () => {
      settings[key] = chosen.includes(v) ? chosen.filter((x) => x !== v) : [...chosen, v];
      changed();
    }));
  }
}

function renderSeg(el, key, cast = String) {
  for (const b of el.querySelectorAll("button")) {
    b.setAttribute("aria-pressed", String(settings[key]) === b.dataset.v);
    b.onclick = () => { settings[key] = cast(b.dataset.v); changed(); };
  }
}

let meta;
async function loadSetup() {
  meta = await api("/api/meta");
  const s = meta.stats;
  $("stats").textContent = s.seen
    ? `You've named ${s.known} of ${s.total} federations` + (s.misses ? `, ${s.misses} to have another go at.` : ".")
    : `${s.total} federations to learn.`;
  // Drop remembered choices that no longer exist.
  settings.continents = settings.continents.filter((c) => meta.continents.some((x) => x.continent === c));
  changed();
}

let poolTimer;
function changed() {
  save();
  renderChips($("continents"), meta.continents, "continents", "continent", "Whole world");
  renderSeg($("mode"), "mode");
  renderSeg($("length"), "length", Number);
  clearTimeout(poolTimer);
  poolTimer = setTimeout(async () => {
    const { pool } = await api(`/api/pool?${query()}`);
    $("pool").textContent = pool
      ? `${pool.toLocaleString()} ${pool === 1 ? "blade matches" : "blades match"}`
      : settings.mode === "misses" ? "No misses here: nothing to retry" : "No blades match these settings";
    $("start").disabled = !pool;
  }, 120);
}

/* ---------- Quiz ---------- */

function startRound() {
  round = { total: settings.length, n: 0, score: 0, items: [] };
  upcoming = null;
  show("quiz");
  nextQuestion();
}

let upcoming = null; // next question, fetched while the answer is on screen

function fetchQuestion() {
  return api(`/api/question?${query({
    exclude: seen.slice(-500).join(","),
    round: round.items.map((i) => i.blade.id).join(","),
  })}`);
}

function prefetch() {
  if (round.total && round.n >= round.total) return;
  upcoming = fetchQuestion();
  upcoming.then((q) => { if (q.img) new Image().src = q.img; }).catch(() => {});
}

async function nextQuestion() {
  if (round.total && round.n >= round.total) return finish();
  let q;
  try {
    q = await (upcoming || fetchQuestion());
    upcoming = null;
  } catch (e) {
    upcoming = null;
    if (round.items.length) return finish();
    return backToSetup(); // nothing left to ask; the setup screen says why
  }
  if (q.done) return finish(); // every blade in these settings has had its turn this round
  round.n += 1;
  current = { id: q.id, hints: 0, wrong: 0, done: false, lastGuess: "" };
  seen.push(q.id);

  $("oar").src = q.img;
  const b = document.createElement("b");
  b.textContent = q.continent;
  $("from").replaceChildren("A federation from ", b);
  $("guess").value = "";
  $("guess").disabled = false;
  $("feedback").textContent = "";
  $("feedback").className = "feedback";
  $("hints").replaceChildren();
  $("hint").disabled = false;
  $("ask").hidden = false;
  $("helpers").hidden = false;
  $("result").hidden = true;
  updateMeta();
  $("guess").focus();
}

function updateMeta() {
  const done = round.total ? (round.n - (current && !current.done ? 1 : 0)) / round.total : 0;
  $("bar").style.width = round.total ? `${done * 100}%` : "0";
  $("count").textContent = round.total ? `${round.n} of ${round.total}` : `Blade ${round.n}`;
  $("score").textContent = `${round.score} pts`;
}

$("ask").onsubmit = async (e) => {
  e.preventDefault();
  const guess = $("guess").value.trim();
  if (!guess || current.done) return;
  current.lastGuess = guess;
  const r = await api("/api/answer", { id: current.id, guess, hints: current.hints, tries: current.wrong + 1 });
  const fb = $("feedback");
  if (r.result === "correct") {
    const pts = Math.max(1, 3 - current.hints - current.wrong);
    return conclude(r.blade, pts);
  }
  if (r.result === "close") {
    fb.textContent = "Close. Check the spelling, or give a bit more of the name.";
    fb.className = "feedback close";
  } else {
    current.wrong += 1;
    fb.textContent = current.wrong === 1 ? "Not this one." : `Not this one either (${current.wrong} wrong).`;
    fb.className = "feedback wrong";
    $("guess").classList.remove("shake");
    void $("guess").offsetWidth;
    $("guess").classList.add("shake");
  }
  $("guess").select();
};

$("hint").onclick = async () => {
  if (current.done || current.hints >= 3) return;
  const h = await api(`/api/hint/${current.id}/${current.hints + 1}`);
  current.hints += 1;
  const li = document.createElement("li");
  const b = document.createElement("b");
  b.textContent = h.label;
  li.append(b, h.text);
  $("hints").append(li);
  $("hint").disabled = current.hints >= 3;
  $("guess").focus();
};

$("giveup").onclick = async () => {
  if (current.done) return;
  const r = await api("/api/reveal", { id: current.id, hints: current.hints, tries: current.wrong, guess: current.lastGuess });
  conclude(r.blade, 0);
};

function conclude(blade, pts) {
  current.done = true;
  round.score += pts;
  round.items.push({ blade, pts });
  $("ask").hidden = true;
  $("helpers").hidden = true;
  $("feedback").textContent = "";

  const v = $("verdict");
  v.textContent = pts ? `Correct, +${pts}` : "This one was";
  v.className = `verdict ${pts ? "good" : "bad"}`;
  $("r-name").textContent = blade.name;
  $("r-sub").textContent = `${blade.code} · ${blade.continent}`;
  $("r-kind").textContent = blade.wr_name ? `World Rowing calls it ${blade.wr_name}` : "";

  $("result").hidden = false;
  updateMeta();
  $("next").textContent = round.total && round.n >= round.total ? "See results" : "Next";
  $("next").focus();
  prefetch();
}

$("next").onclick = nextQuestion;
$("stop").onclick = () => (round.items.length ? finish() : backToSetup());

/* ---------- Summary ---------- */

function finish() {
  const items = round.items;
  const max = items.length * 3;
  const right = items.filter((i) => i.pts > 0).length;
  $("s-title").textContent = `${round.score} of ${max} points`;
  $("s-line").textContent = items.length
    ? `You named ${right} of ${items.length} blades.` + (right < items.length ? " The ones you missed are saved under \"My misses\"." : "")
    : "No blades answered.";
  const list = $("recap");
  list.replaceChildren();
  for (const { blade, pts } of items) {
    const li = document.createElement("li");
    const img = document.createElement("img");
    img.src = `/img/${blade.id}`;
    img.alt = blade.name;
    const who = document.createElement("div");
    who.className = "who";
    who.textContent = blade.name;
    const small = document.createElement("small");
    small.textContent = `${blade.code} · ${blade.continent}`;
    who.append(small);
    const p = document.createElement("span");
    p.className = `pts ${pts ? "good" : "bad"}`;
    p.textContent = pts ? `+${pts}` : "missed";
    li.append(img, who, p);
    list.append(li);
  }
  show("summary");
  $("again").focus();
}

function backToSetup() {
  show("setup");
  loadSetup();
}

$("start").onclick = startRound;
$("again").onclick = startRound;
$("change").onclick = backToSetup;
$("home").onclick = () => {
  if (round && round.items.length && !$("quiz").hidden && !confirm("Leave this round?")) return;
  backToSetup();
};

loadSetup();
