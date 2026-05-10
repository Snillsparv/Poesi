#!/usr/bin/env python3
"""Generera en HTML-dashboard över diktbedömningarna.

Läser results/raw_komplett.json och skriver results/dashboard.html.
Öppna sedan filen direkt i webbläsaren.
"""

import json
import sys
from pathlib import Path
from statistics import mean, pstdev


DIKT_NAMES = {
    "1": "Stjärnorna",
    "2": "Den som väntar på något gott",
    "3": "Ett väldigt bra recept",
    "4": "Smittsamt",
    "5": "Hela havet stormar",
    "6": "Förnuft och känsla",
    "7": "Konstvärk",
    "8": "Ultraviolens",
}


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
    """form_scores: list[(dikt, score)]. Returnera dikt -> placering (1 = högst).
    Lika poäng → medelplacering."""
    sorted_items = sorted(form_scores, key=lambda x: -x[1])
    ranks: dict[str, float] = {}
    i = 0
    n = len(sorted_items)
    while i < n:
        j = i
        while j < n and sorted_items[j][1] == sorted_items[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        for k in range(i, j):
            ranks[sorted_items[k][0]] = avg_rank
        i = j
    return ranks


def main() -> None:
    src = Path("results/raw_komplett.json")
    if not src.is_file():
        sys.exit(f"Hittar inte {src}. Kör filter_complete.py först.")
    data = json.loads(src.read_text(encoding="utf-8"))

    per_score: dict[str, list[float]] = {k: [] for k in DIKT_NAMES}
    per_norm: dict[str, list[float]] = {k: [] for k in DIKT_NAMES}
    per_comments: dict[str, list[dict]] = {k: [] for k in DIKT_NAMES}
    fav_count: dict[str, int] = {k: 0 for k in DIKT_NAMES}
    worst_count: dict[str, int] = {k: 0 for k in DIKT_NAMES}

    for img, entry in data.items():
        ovrig = entry.get("ovrig_text") or ""
        form_scores: list[tuple[str, float]] = []
        for r in entry.get("rader", []):
            d = str(r.get("diktnummer") or "").strip()
            score = chosen_score(r)
            if d not in DIKT_NAMES or score is None:
                continue
            form_scores.append((d, score))
            per_score[d].append(score)
            kom = (r.get("kommentar") or "").strip()
            minne = (r.get("minnesanteckning") or "").strip()
            if kom or minne:
                per_comments[d].append({
                    "bild": img,
                    "lasare": ovrig,
                    "poang": score,
                    "minnesanteckning": minne,
                    "kommentar": kom,
                })
        for d, rk in fractional_ranks(form_scores).items():
            per_norm[d].append(rk)
        if form_scores:
            top = max(s for _, s in form_scores)
            bot = min(s for _, s in form_scores)
            for d, s in form_scores:
                if s == top:
                    fav_count[d] += 1
                if s == bot:
                    worst_count[d] += 1

    rows = []
    for nr, namn in DIKT_NAMES.items():
        s = per_score[nr]
        nrm = per_norm[nr]
        rows.append({
            "nr": nr,
            "namn": namn,
            "antal": len(s),
            "snitt": round(mean(s), 3) if s else None,
            "stddev": round(pstdev(s), 3) if len(s) > 1 else 0,
            "total": round(sum(s), 2),
            "norm_snitt": round(mean(nrm), 3) if nrm else None,
            "norm_stddev": round(pstdev(nrm), 3) if len(nrm) > 1 else 0,
            "norm_total": round(sum(nrm), 2),
            "favoriter": fav_count[nr],
            "samst": worst_count[nr],
            "kommentarer": sorted(per_comments[nr], key=lambda c: -c["poang"]),
        })

    out = Path("results/dashboard.html")
    out.write_text(render_html(rows, len(data)), encoding="utf-8")
    print(f"Skrev {out} ({len(data)} formulär, {sum(r['antal'] for r in rows)} poäng)")


def render_html(rows: list[dict], n_forms: int) -> str:
    n_scores = sum(r["antal"] for r in rows)
    return (HTML_TEMPLATE
            .replace("__N_FORMS__", str(n_forms))
            .replace("__N_SCORES__", str(n_scores))
            .replace("__ROWS__", json.dumps(rows, ensure_ascii=False)))


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
  header.hero { text-align: center; margin-bottom: 3rem; }
  .eyebrow { color: var(--accent); font-size: .8rem; font-weight: 600; letter-spacing: .15em; text-transform: uppercase; margin-bottom: .5rem; }
  h1 { font-family: 'Georgia', 'Times New Roman', serif; font-size: 2.6rem; font-weight: 400; margin: 0 0 .75rem; letter-spacing: -.01em; }
  .lead { color: var(--ink-soft); font-size: 1.05rem; max-width: 540px; margin: 0 auto; }
  .lead strong { color: var(--ink); font-weight: 600; }

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
  td.nr { color: var(--ink-muted); width: 2em; }
  td.rank { font-weight: 600; color: var(--accent); width: 2em; text-align: center; }

  .bar-row { display: flex; align-items: center; gap: .75rem; }
  .bar-row .label { flex: 0 0 auto; min-width: 12rem; font-weight: 500; }
  .bar-row .label .nr { color: var(--ink-muted); margin-right: .4em; font-weight: 400; }
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
  }

  #comments { scroll-margin-top: 1rem; }
  #comments.empty .empty-msg { color: var(--ink-muted); font-style: italic; text-align: center; padding: 2rem 0; }
  .comment { padding: 1rem 0; border-bottom: 1px solid var(--line-soft); }
  .comment:last-child { border-bottom: none; }
  .comment-head { display: flex; gap: .85rem; align-items: baseline; flex-wrap: wrap; margin-bottom: .35rem; }
  .comment-head .reader { font-weight: 600; color: var(--ink); }
  .comment-head .score { color: var(--accent); font-weight: 700; font-variant-numeric: tabular-nums; }
  .comment-head .img { color: var(--ink-muted); font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: .75rem; margin-left: auto; }
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
  <p class="lead"><strong>__N_FORMS__</strong> formulär · <strong>8</strong> dikter · <strong>__N_SCORES__</strong> poäng</p>
</header>

<section>
  <h2>Pallplatser</h2>
  <div class="section-sub">Sorterat efter genomsnittlig poäng. Klicka på ett kort för att läsa kommentarer.</div>
  <div class="podium" id="podium"></div>
</section>

<section>
  <h2>Alla dikter</h2>
  <div class="section-sub">Klicka på en kolumnrubrik för att sortera om. Klicka på en dikt för att läsa kommentarer.</div>
  <table id="main-table">
    <thead><tr>
      <th class="num sortable" data-key="nr">#</th>
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
    <div id="fav-bars"></div>
  </section>
  <section class="tight">
    <h2>▼ Sämst</h2>
    <div class="section-sub">Antal formulär där dikten fick lägsta poängen.</div>
    <div id="worst-bars"></div>
  </section>
</div>

<section>
  <h2>Normaliserad rangordning</h2>
  <div class="section-sub">I varje formulär ersätts poängen med diktens placering 1–8 (1 = bäst, lika poäng → medelplacering). Lägre värde = bättre.</div>
  <table id="norm-table">
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
    <strong>Varför två sätt?</strong> Snitt-rankningen mäter absolut uppskattning (4.2 av 5 osv). Den normaliserade rankningen ignorerar att olika personer betygsätter olika hårt — bara ordningen inom varje formulär räknas. När båda pekar åt samma håll är resultatet stabilt.
  </div>
</section>

<section id="comments-section">
  <h2 id="comment-header">Kommentarer</h2>
  <div id="comments" class="empty">
    <div class="empty-msg">Klicka på en dikt för att se kommentarerna.</div>
  </div>
</section>

</div>

<script>
const ROWS = __ROWS__;

function computeRanks() {
  const byTotal = [...ROWS].sort((a, b) => b.snitt - a.snitt);
  byTotal.forEach((r, i) => r.rank_total = i + 1);
  const byNorm = [...ROWS].sort((a, b) => a.norm_snitt - b.norm_snitt);
  byNorm.forEach((r, i) => r.rank_norm = i + 1);
}
computeRanks();

let sortKey = 'snitt';
let sortDir = -1;

function fmt(v, d = 2) {
  if (v === null || v === undefined || v === '') return '';
  if (typeof v === 'number') return v.toFixed(d);
  return v;
}

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function renderPodium() {
  const top3 = [...ROWS].sort((a, b) => b.snitt - a.snitt).slice(0, 3);
  const order = [top3[1], top3[0], top3[2]];
  const tier = ['silver', 'gold', 'bronze'];
  const medal = ['🥈', '🥇', '🥉'];
  const place = ['Andra plats', 'Första plats', 'Tredje plats'];
  document.getElementById('podium').innerHTML = order.map((r, i) => `
    <div class="pod ${tier[i]}" data-nr="${r.nr}">
      <div class="medal">${medal[i]}</div>
      <div class="place">${place[i]}</div>
      <div class="pname">${escapeHtml(r.namn)}</div>
      <div class="pscore">${r.snitt.toFixed(2)}</div>
      <div class="pmeta">snitt · ${r.favoriter} favoriter</div>
    </div>
  `).join('');
  document.querySelectorAll('.pod').forEach(el => el.addEventListener('click', () => showComments(el.dataset.nr)));
}

function renderMain() {
  const tbody = document.querySelector('#main-table tbody');
  const sorted = [...ROWS].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey];
    if (typeof av === 'string') return sortDir * av.localeCompare(bv, 'sv');
    return sortDir * ((av ?? 0) - (bv ?? 0));
  });
  tbody.innerHTML = sorted.map(r => `
    <tr class="poem" data-nr="${r.nr}">
      <td class="nr num">${r.nr}</td>
      <td class="name">${escapeHtml(r.namn)}</td>
      <td class="num">${fmt(r.snitt)}</td>
      <td class="num">${fmt(r.stddev)}</td>
      <td class="num">${fmt(r.total, 1)}</td>
      <td class="num">${r.favoriter}</td>
      <td class="num">${r.samst}</td>
    </tr>
  `).join('');
  document.querySelectorAll('#main-table th.sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.key === sortKey) th.classList.add(sortDir < 0 ? 'sort-desc' : 'sort-asc');
  });
  document.querySelectorAll('tr.poem').forEach(tr => {
    tr.addEventListener('click', () => showComments(tr.dataset.nr));
  });
}

function renderBars(elId, key, cls) {
  const sorted = [...ROWS].sort((a, b) => b[key] - a[key]);
  const max = Math.max(...sorted.map(r => r[key])) || 1;
  document.getElementById(elId).innerHTML = sorted.map(r => `
    <div class="bar-row" data-nr="${r.nr}" style="cursor:pointer; padding:.35rem 0;">
      <div class="label"><span class="nr">${r.nr}.</span>${escapeHtml(r.namn)}</div>
      <div class="bar-track"><div class="bar-fill ${cls}" style="width:${(r[key] / max * 100).toFixed(1)}%"></div></div>
      <div class="count">${r[key]}</div>
    </div>
  `).join('');
  document.querySelectorAll('#' + elId + ' .bar-row').forEach(el =>
    el.addEventListener('click', () => showComments(el.dataset.nr)));
}

function renderNorm() {
  const sorted = [...ROWS].sort((a, b) => a.norm_snitt - b.norm_snitt);
  document.querySelector('#norm-table tbody').innerHTML = sorted.map((r, i) => `
    <tr class="poem" data-nr="${r.nr}">
      <td class="rank">${i + 1}</td>
      <td class="name"><span class="nr" style="color:#8a8a96; margin-right:.4em">${r.nr}.</span>${escapeHtml(r.namn)}</td>
      <td class="num">${r.norm_snitt.toFixed(2)}</td>
      <td class="num">${r.norm_stddev.toFixed(2)}</td>
      <td class="num">${r.norm_total.toFixed(1)}</td>
    </tr>
  `).join('');
  document.querySelectorAll('#norm-table tr.poem').forEach(tr =>
    tr.addEventListener('click', () => showComments(tr.dataset.nr)));
}

function showComments(nr) {
  document.querySelectorAll('tr.poem').forEach(tr => tr.classList.toggle('active', tr.dataset.nr === nr));
  const row = ROWS.find(r => r.nr === nr);
  const div = document.getElementById('comments');
  document.getElementById('comment-header').textContent = `Kommentarer — ${nr}. ${row.namn} (${row.kommentarer.length} st)`;
  if (row.kommentarer.length === 0) {
    div.className = 'empty';
    div.innerHTML = '<div class="empty-msg">Inga kommentarer eller minnesanteckningar för denna dikt.</div>';
  } else {
    div.className = '';
    div.innerHTML = row.kommentarer.map(c => `
      <div class="comment">
        <div class="comment-head">
          <span class="reader">${escapeHtml(c.lasare || '(okänd läsare)')}</span>
          <span class="score">${c.poang.toFixed(1)}</span>
          <span class="img">${escapeHtml(c.bild)}</span>
        </div>
        ${c.minnesanteckning ? `<div class="minne">${escapeHtml(c.minnesanteckning)}</div>` : ''}
        ${c.kommentar ? `<div>${escapeHtml(c.kommentar)}</div>` : ''}
      </div>
    `).join('');
  }
  document.getElementById('comment-header').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

document.querySelectorAll('th.sortable').forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.key;
    if (sortKey === key) sortDir = -sortDir;
    else { sortKey = key; sortDir = th.dataset.default === 'asc' ? 1 : -1; }
    renderMain();
  });
});

renderPodium();
renderMain();
renderBars('fav-bars', 'favoriter', 'fav');
renderBars('worst-bars', 'samst', 'worst');
renderNorm();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
