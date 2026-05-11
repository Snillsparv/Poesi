#!/usr/bin/env python3
"""Generera en HTML-dashboard över alla omgångar av diktbedömningar.

Skriver results/dashboard.html med flikar för varje omgång samt totalt.
Lägger till nya omgångar genom att utöka ROUNDS-listan nedan.
"""

import json
import sys
from pathlib import Path
from statistics import mean, pstdev


ROUNDS = [
    {
        "id": "omg1",
        "label": "Omgång 1",
        "path": "results/raw_komplett.json",
        "dikter": {
            "1": "Stjärnorna",
            "2": "Den som väntar på något gott",
            "3": "Ett väldigt bra recept",
            "4": "Smittsamt",
            "5": "Hela havet stormar",
            "6": "Förnuft och känsla",
            "7": "Konstvärk",
            "8": "Ultraviolens",
        },
    },
    {
        "id": "omg2",
        "label": "Omgång 2",
        "path": "results2/raw_komplett.json",
        "dikter": {
            "1": "Ultraviolens",
            "2": "Stjärnorna",
            "3": "Konstvärk",
            "4": "Hela havet stormar",
            "5": "Smittsamt",
            "6": "Den som väntar på något gott",
            "7": "Ett väldigt bra recept",
            "8": "Förnuft och känsla",
        },
    },
]


def parse_score(s):
    if s is None:
        return None
    try:
        return float(str(s).strip().replace(",", "."))
    except ValueError:
        return None


def chosen_score(row):
    alla = row.get("poang_alla") or []
    if alla:
        return parse_score(alla[-1])
    return parse_score(row.get("poang_officiell"))


def fractional_ranks(form_scores):
    """form_scores: list[(key, score)]. Returnera key -> placering (1 = högst).
    Lika poäng → medelplacering."""
    sorted_items = sorted(form_scores, key=lambda x: -x[1])
    ranks: dict = {}
    i = 0
    n = len(sorted_items)
    while i < n:
        j = i
        while j < n and sorted_items[j][1] == sorted_items[i][1]:
            j += 1
        avg = (i + 1 + j) / 2
        for k in range(i, j):
            ranks[sorted_items[k][0]] = avg
        i = j
    return ranks


def load_forms(round_cfg) -> list[dict]:
    src = Path(round_cfg["path"])
    if not src.is_file():
        sys.exit(f"Hittar inte {src}. Kör filter_complete.py först för den omgången.")
    data = json.loads(src.read_text(encoding="utf-8"))
    mapping = round_cfg["dikter"]
    forms = []
    for img, entry in data.items():
        reader = entry.get("ovrig_text") or ""
        rader = []
        for r in entry.get("rader", []):
            nr = str(r.get("diktnummer") or "").strip()
            poem = mapping.get(nr)
            score = chosen_score(r)
            if not poem or score is None:
                continue
            rader.append({
                "poem": poem,
                "score": score,
                "kommentar": (r.get("kommentar") or "").strip(),
                "minnesanteckning": (r.get("minnesanteckning") or "").strip(),
            })
        forms.append({"img": img, "reader": reader, "round": round_cfg["id"], "rader": rader})
    return forms


def compute_rows(forms: list[dict], poems: list[str]) -> list[dict]:
    per_score: dict[str, list[float]] = {p: [] for p in poems}
    per_norm: dict[str, list[float]] = {p: [] for p in poems}
    per_comments: dict[str, list[dict]] = {p: [] for p in poems}
    fav: dict[str, int] = {p: 0 for p in poems}
    worst: dict[str, int] = {p: 0 for p in poems}

    for f in forms:
        pairs = [(r["poem"], r["score"]) for r in f["rader"]]
        for r in f["rader"]:
            per_score[r["poem"]].append(r["score"])
            if r["kommentar"] or r["minnesanteckning"]:
                per_comments[r["poem"]].append({
                    "bild": f["img"],
                    "lasare": f["reader"],
                    "poang": r["score"],
                    "minnesanteckning": r["minnesanteckning"],
                    "kommentar": r["kommentar"],
                    "omg": f["round"],
                })
        for p, rk in fractional_ranks(pairs).items():
            per_norm[p].append(rk)
        if pairs:
            top = max(s for _, s in pairs)
            bot = min(s for _, s in pairs)
            for p, s in pairs:
                if s == top:
                    fav[p] += 1
                if s == bot:
                    worst[p] += 1

    rows = []
    for poem in poems:
        s = per_score[poem]
        nm = per_norm[poem]
        rows.append({
            "namn": poem,
            "antal": len(s),
            "snitt": round(mean(s), 3) if s else None,
            "stddev": round(pstdev(s), 3) if len(s) > 1 else 0,
            "total": round(sum(s), 2),
            "norm_snitt": round(mean(nm), 3) if nm else None,
            "norm_stddev": round(pstdev(nm), 3) if len(nm) > 1 else 0,
            "norm_total": round(sum(nm), 2),
            "favoriter": fav[poem],
            "samst": worst[poem],
            "kommentarer": sorted(per_comments[poem], key=lambda c: -c["poang"]),
        })
    return rows


def main() -> None:
    canonical_poems = list(dict.fromkeys(
        p for r in ROUNDS for p in r["dikter"].values()
    ))
    tabs = []
    all_forms: list[dict] = []
    for r in ROUNDS:
        forms = load_forms(r)
        all_forms.extend(forms)
        rows = compute_rows(forms, list(r["dikter"].values()))
        tabs.append({
            "id": r["id"],
            "label": r["label"],
            "n_forms": len(forms),
            "n_scores": sum(row["antal"] for row in rows),
            "rows": rows,
        })
    total_rows = compute_rows(all_forms, canonical_poems)
    tabs.append({
        "id": "total",
        "label": "Totalt",
        "n_forms": len(all_forms),
        "n_scores": sum(row["antal"] for row in total_rows),
        "rows": total_rows,
    })

    out = Path("results/dashboard.html")
    out.write_text(render_html(tabs), encoding="utf-8")
    print(f"Skrev {out}")
    for t in tabs:
        print(f"  {t['label']}: {t['n_forms']} formulär, {t['n_scores']} poäng")


def render_html(tabs: list[dict]) -> str:
    return HTML_TEMPLATE.replace("__TABS__", json.dumps(tabs, ensure_ascii=False))


HTML_TEMPLATE = r"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dikt-dashboard</title>
<style>
  :root {
    --bg: #f7f5f0;
    --card: #ffffff;
    --ink: #1f1f24;
    --ink-soft: #5a5a66;
    --ink-muted: #8a8a96;
    --line: #e6e3dc;
    --line-soft: #f0ede6;
    --accent: #b34a3a;
    --accent-soft: #faf0ee;
    --gold: #c9a23a;
    --gold-soft: #fbf5e2;
    --silver: #9aa0a6;
    --silver-soft: #f1f2f4;
    --bronze: #b27a4a;
    --bronze-soft: #f7eee5;
    --shadow: 0 1px 2px rgba(0,0,0,.04), 0 6px 24px rgba(20,20,30,.06);
  }
  * { box-sizing: border-box; }
  html, body { background: var(--bg); color: var(--ink); }
  body { font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 3rem 1.5rem 5rem; line-height: 1.5; }
  .wrap { max-width: 960px; margin: 0 auto; }
  header.hero { text-align: center; margin-bottom: 2.5rem; }
  .eyebrow { color: var(--accent); font-size: .8rem; font-weight: 600; letter-spacing: .15em; text-transform: uppercase; margin-bottom: .5rem; }
  h1 { font-family: 'Georgia', 'Times New Roman', serif; font-size: 2.6rem; font-weight: 400; margin: 0 0 .75rem; letter-spacing: -.01em; }
  .lead { color: var(--ink-soft); font-size: 1.05rem; max-width: 540px; margin: 0 auto; }
  .lead strong { color: var(--ink); font-weight: 600; }

  nav.tabs { display: flex; gap: .25rem; background: var(--card); border-radius: 12px; padding: .35rem; margin-bottom: 1.5rem; box-shadow: var(--shadow); }
  .tab { flex: 1; background: transparent; border: none; padding: .85rem 1rem; font-size: .95rem; font-weight: 500; color: var(--ink-soft); border-radius: 9px; cursor: pointer; font-family: inherit; transition: background .15s, color .15s; }
  .tab:hover { color: var(--ink); background: var(--line-soft); }
  .tab.active { background: var(--accent); color: white; }
  .tab .count { display: block; font-size: .7rem; font-weight: 400; opacity: .8; margin-top: .15rem; letter-spacing: .05em; }

  section { background: var(--card); border-radius: 12px; padding: 2rem 2.25rem; margin-bottom: 1.5rem; box-shadow: var(--shadow); }
  section.tight { padding: 1.5rem 2.25rem; }
  h2 { font-family: 'Georgia', serif; font-size: 1.35rem; font-weight: 400; margin: 0 0 .25rem; letter-spacing: -.005em; }
  .section-sub { color: var(--ink-muted); font-size: .85rem; margin-bottom: 1.25rem; }

  .podium { display: grid; grid-template-columns: 1fr 1.2fr 1fr; gap: 1rem; margin-top: .5rem; align-items: end; }
  .pod { border-radius: 10px; padding: 1.25rem 1rem; text-align: center; transition: transform .15s; cursor: pointer; }
  .pod:hover { transform: translateY(-2px); }
  .pod.gold { background: var(--gold-soft); border: 1px solid #f0e3b8; }
  .pod.silver { background: var(--silver-soft); border: 1px solid #e1e3e7; }
  .pod.bronze { background: var(--bronze-soft); border: 1px solid #ecd9c3; }
  .pod .medal { font-size: 1.6rem; margin-bottom: .25rem; }
  .pod .place { font-size: .75rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-soft); }
  .pod.gold .place { color: var(--gold); }
  .pod.silver .place { color: var(--silver); }
  .pod.bronze .place { color: var(--bronze); }
  .pod .pname { font-family: 'Georgia', serif; font-size: 1.15rem; margin: .35rem 0 .25rem; line-height: 1.2; }
  .pod .pmeta { color: var(--ink-muted); font-size: .8rem; }
  .pod .pscore { font-size: 1.5rem; font-weight: 600; margin-top: .25rem; font-variant-numeric: tabular-nums; }

  table { border-collapse: collapse; width: 100%; font-size: .95rem; }
  th, td { padding: .7rem .85rem; text-align: left; border-bottom: 1px solid var(--line-soft); }
  thead th { font-size: .75rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-muted); border-bottom: 1px solid var(--line); }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr.poem { cursor: pointer; transition: background .12s; }
  tbody tr.poem:hover td { background: var(--accent-soft); }
  tbody tr.poem.active td { background: var(--accent-soft); box-shadow: inset 3px 0 0 var(--accent); }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  td.name { font-weight: 500; }
  td.rank { font-weight: 600; color: var(--accent); width: 2em; text-align: center; }

  .bar-row { display: flex; align-items: center; gap: .75rem; cursor: pointer; padding: .35rem 0; }
  .bar-row .label { flex: 0 0 auto; min-width: 12rem; font-weight: 500; }
  .bar-track { flex: 1; height: .6rem; background: var(--line-soft); border-radius: 100px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 100px; }
  .bar-fill.fav { background: linear-gradient(90deg, #c9a23a, #d9b860); }
  .bar-fill.worst { background: linear-gradient(90deg, #b34a3a, #c97264); }
  .bar-row .count { flex: 0 0 2.5em; text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  @media (max-width: 720px) {
    body { padding: 2rem 1rem 3rem; }
    h1 { font-size: 2rem; }
    .grid-2 { grid-template-columns: 1fr; }
    .podium { grid-template-columns: 1fr; }
    section { padding: 1.5rem; }
    nav.tabs { flex-direction: column; }
  }

  .comments-area { scroll-margin-top: 1rem; }
  .comments-area.empty .empty-msg { color: var(--ink-muted); font-style: italic; text-align: center; padding: 2rem 0; }
  .comment { padding: 1rem 0; border-bottom: 1px solid var(--line-soft); }
  .comment:last-child { border-bottom: none; }
  .comment-head { display: flex; gap: .85rem; align-items: baseline; flex-wrap: wrap; margin-bottom: .35rem; }
  .comment-head .reader { font-weight: 600; color: var(--ink); }
  .comment-head .score { color: var(--accent); font-weight: 700; font-variant-numeric: tabular-nums; }
  .comment-head .img { color: var(--ink-muted); font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: .75rem; margin-left: auto; }
  .comment-head .omg-badge { font-size: .7rem; background: var(--line-soft); color: var(--ink-soft); padding: .1rem .45rem; border-radius: 99px; }
  .minne { color: var(--ink-soft); font-style: italic; margin-bottom: .15rem; }
  .minne::before { content: '✎ '; color: var(--ink-muted); }
  .info { font-size: .8rem; color: var(--ink-muted); padding: 1rem 1.25rem; background: var(--line-soft); border-radius: 8px; margin-top: 1rem; line-height: 1.55; }
  .info strong { color: var(--ink-soft); }
  .sortable { cursor: pointer; user-select: none; }
  .sortable:hover { color: var(--ink); }
  .sortable.sort-asc::after { content: ' ↑'; color: var(--accent); }
  .sortable.sort-desc::after { content: ' ↓'; color: var(--accent); }
</style>
</head>
<body>
<div class="wrap">

<header class="hero">
  <div class="eyebrow">Resultatsammanställning</div>
  <h1>Dikter i siffror</h1>
  <p class="lead" id="hero-lead"></p>
</header>

<nav class="tabs" id="tabs"></nav>

<div id="panels"></div>

</div>

<script>
const TABS = __TABS__;
const ROUND_LABELS = Object.fromEntries(TABS.map(t => [t.id, t.label]));

const tabsEl = document.getElementById('tabs');
const panelsEl = document.getElementById('panels');

TABS.forEach((t, i) => {
  const btn = document.createElement('button');
  btn.className = 'tab' + (i === 0 ? ' active' : '');
  btn.dataset.tab = t.id;
  btn.innerHTML = `${escapeHtml(t.label)}<span class="count">${t.n_forms} formulär · ${t.n_scores} poäng</span>`;
  btn.addEventListener('click', () => activateTab(t.id));
  tabsEl.appendChild(btn);

  const panel = document.createElement('div');
  panel.id = 'panel-' + t.id;
  panel.className = 'tab-panel';
  panel.hidden = i !== 0;
  panelsEl.appendChild(panel);
  renderPanel(panel, t);
});

function activateTab(id) {
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === id));
  document.querySelectorAll('.tab-panel').forEach(p => p.hidden = p.id !== 'panel-' + id);
  const t = TABS.find(x => x.id === id);
  document.getElementById('hero-lead').innerHTML = `<strong>${t.label}</strong> — ${t.n_forms} formulär, ${t.n_scores} poäng.`;
}
activateTab(TABS[0].id);

function renderPanel(panel, tab) {
  const rows = tab.rows.map(r => ({...r}));
  computeRanks(rows);
  panel.innerHTML = `
    <section>
      <h2>Pallplatser</h2>
      <div class="section-sub">Sorterat efter genomsnittlig poäng. Klicka på ett kort för att läsa kommentarer.</div>
      <div class="podium"></div>
    </section>
    <section>
      <h2>Alla dikter</h2>
      <div class="section-sub">Klicka på en kolumnrubrik för att sortera om. Klicka på en dikt för att läsa kommentarer.</div>
      <table class="main-table">
        <thead><tr>
          <th class="sortable" data-key="namn">Dikt</th>
          <th class="num sortable" data-key="snitt" data-default="desc">Snitt</th>
          <th class="num sortable" data-key="stddev">Std.avv.</th>
          <th class="num sortable" data-key="total">Total</th>
          <th class="num sortable" data-key="favoriter">★ Favorit</th>
          <th class="num sortable" data-key="samst">▼ Sämst</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </section>
    <div class="grid-2">
      <section class="tight">
        <h2>★ Favorit</h2>
        <div class="section-sub">Antal formulär där dikten fick högsta poängen.</div>
        <div class="fav-bars"></div>
      </section>
      <section class="tight">
        <h2>▼ Sämst</h2>
        <div class="section-sub">Antal formulär där dikten fick lägsta poängen.</div>
        <div class="worst-bars"></div>
      </section>
    </div>
    <section>
      <h2>Normaliserad rangordning</h2>
      <div class="section-sub">I varje formulär ersätts poängen med diktens placering 1–8 (1 = bäst, lika poäng → medelplacering). Lägre värde = bättre.</div>
      <table class="norm-table">
        <thead><tr>
          <th class="num">Rang</th>
          <th>Dikt</th>
          <th class="num">Snittplacering</th>
          <th class="num">Std.avv.</th>
          <th class="num">Summa placeringar</th>
        </tr></thead>
        <tbody></tbody>
      </table>
      <div class="info">
        <strong>Varför två sätt?</strong> Snitt-rankningen mäter absolut uppskattning (4.2 av 5). Den normaliserade ignorerar att olika personer betygsätter olika hårt — bara ordningen inom varje formulär räknas. När båda pekar åt samma håll är resultatet stabilt.
      </div>
    </section>
    <section class="comments-section">
      <h2 class="comment-header">Kommentarer</h2>
      <div class="comments-area empty">
        <div class="empty-msg">Klicka på en dikt för att se kommentarerna.</div>
      </div>
    </section>
  `;

  const state = { sortKey: 'snitt', sortDir: -1, rows };
  renderPodium(panel, state);
  renderMain(panel, state);
  renderBars(panel.querySelector('.fav-bars'), state.rows, 'favoriter', 'fav', panel);
  renderBars(panel.querySelector('.worst-bars'), state.rows, 'samst', 'worst', panel);
  renderNorm(panel, state);

  panel.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (state.sortKey === key) state.sortDir = -state.sortDir;
      else { state.sortKey = key; state.sortDir = th.dataset.default === 'asc' ? 1 : -1; }
      renderMain(panel, state);
    });
  });
}

function computeRanks(rows) {
  [...rows].sort((a, b) => b.snitt - a.snitt).forEach((r, i) => r.rank_total = i + 1);
  [...rows].sort((a, b) => a.norm_snitt - b.norm_snitt).forEach((r, i) => r.rank_norm = i + 1);
}

function renderPodium(panel, state) {
  const top3 = [...state.rows].sort((a, b) => b.snitt - a.snitt).slice(0, 3);
  const order = [top3[1], top3[0], top3[2]].filter(Boolean);
  const tier = top3.length === 3 ? ['silver', 'gold', 'bronze'] : ['gold'];
  const medal = top3.length === 3 ? ['🥈', '🥇', '🥉'] : ['🥇'];
  const place = top3.length === 3 ? ['Andra plats', 'Första plats', 'Tredje plats'] : ['Första plats'];
  panel.querySelector('.podium').innerHTML = order.map((r, i) => `
    <div class="pod ${tier[i]}" data-name="${escapeHtml(r.namn)}">
      <div class="medal">${medal[i]}</div>
      <div class="place">${place[i]}</div>
      <div class="pname">${escapeHtml(r.namn)}</div>
      <div class="pscore">${r.snitt.toFixed(2)}</div>
      <div class="pmeta">snitt · ${r.favoriter} favoriter</div>
    </div>
  `).join('');
  panel.querySelectorAll('.pod').forEach(el =>
    el.addEventListener('click', () => showComments(panel, el.dataset.name)));
}

function renderMain(panel, state) {
  const sorted = [...state.rows].sort((a, b) => {
    const av = a[state.sortKey], bv = b[state.sortKey];
    if (typeof av === 'string') return state.sortDir * av.localeCompare(bv, 'sv');
    return state.sortDir * ((av ?? 0) - (bv ?? 0));
  });
  panel.querySelector('.main-table tbody').innerHTML = sorted.map(r => `
    <tr class="poem" data-name="${escapeHtml(r.namn)}">
      <td class="name">${escapeHtml(r.namn)}</td>
      <td class="num">${fmt(r.snitt)}</td>
      <td class="num">${fmt(r.stddev)}</td>
      <td class="num">${fmt(r.total, 1)}</td>
      <td class="num">${r.favoriter}</td>
      <td class="num">${r.samst}</td>
    </tr>
  `).join('');
  panel.querySelectorAll('.main-table th.sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.key === state.sortKey) th.classList.add(state.sortDir < 0 ? 'sort-desc' : 'sort-asc');
  });
  panel.querySelectorAll('.main-table tr.poem').forEach(tr =>
    tr.addEventListener('click', () => showComments(panel, tr.dataset.name)));
}

function renderBars(el, rows, key, cls, panel) {
  const sorted = [...rows].sort((a, b) => b[key] - a[key]);
  const max = Math.max(...sorted.map(r => r[key])) || 1;
  el.innerHTML = sorted.map(r => `
    <div class="bar-row" data-name="${escapeHtml(r.namn)}">
      <div class="label">${escapeHtml(r.namn)}</div>
      <div class="bar-track"><div class="bar-fill ${cls}" style="width:${(r[key] / max * 100).toFixed(1)}%"></div></div>
      <div class="count">${r[key]}</div>
    </div>
  `).join('');
  el.querySelectorAll('.bar-row').forEach(row =>
    row.addEventListener('click', () => showComments(panel, row.dataset.name)));
}

function renderNorm(panel, state) {
  const sorted = [...state.rows].sort((a, b) => a.norm_snitt - b.norm_snitt);
  panel.querySelector('.norm-table tbody').innerHTML = sorted.map((r, i) => `
    <tr class="poem" data-name="${escapeHtml(r.namn)}">
      <td class="rank">${i + 1}</td>
      <td class="name">${escapeHtml(r.namn)}</td>
      <td class="num">${r.norm_snitt.toFixed(2)}</td>
      <td class="num">${r.norm_stddev.toFixed(2)}</td>
      <td class="num">${r.norm_total.toFixed(1)}</td>
    </tr>
  `).join('');
  panel.querySelectorAll('.norm-table tr.poem').forEach(tr =>
    tr.addEventListener('click', () => showComments(panel, tr.dataset.name)));
}

function showComments(panel, name) {
  panel.querySelectorAll('tr.poem').forEach(tr => tr.classList.toggle('active', tr.dataset.name === name));
  const tab = TABS.find(t => 'panel-' + t.id === panel.id);
  const row = tab.rows.find(r => r.namn === name);
  const area = panel.querySelector('.comments-area');
  const header = panel.querySelector('.comment-header');
  header.textContent = `Kommentarer — ${name} (${row.kommentarer.length} st)`;
  if (row.kommentarer.length === 0) {
    area.className = 'comments-area empty';
    area.innerHTML = '<div class="empty-msg">Inga kommentarer eller minnesanteckningar för denna dikt.</div>';
  } else {
    area.className = 'comments-area';
    area.innerHTML = row.kommentarer.map(c => `
      <div class="comment">
        <div class="comment-head">
          <span class="reader">${escapeHtml(c.lasare || '(okänd läsare)')}</span>
          <span class="score">${c.poang.toFixed(1)}</span>
          ${c.omg && tab.id === 'total' ? `<span class="omg-badge">${escapeHtml(ROUND_LABELS[c.omg] || c.omg)}</span>` : ''}
          <span class="img">${escapeHtml(c.bild)}</span>
        </div>
        ${c.minnesanteckning ? `<div class="minne">${escapeHtml(c.minnesanteckning)}</div>` : ''}
        ${c.kommentar ? `<div>${escapeHtml(c.kommentar)}</div>` : ''}
      </div>
    `).join('');
  }
  header.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function fmt(v, d = 2) {
  if (v === null || v === undefined || v === '') return '';
  if (typeof v === 'number') return v.toFixed(d);
  return v;
}

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
