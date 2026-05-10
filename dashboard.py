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
    return HTML_TEMPLATE.replace("__N_FORMS__", str(n_forms)).replace(
        "__ROWS__", json.dumps(rows, ensure_ascii=False)
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<title>Dikt-dashboard</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 1.5rem; background: #111; color: #eee; max-width: 1100px; }
  h1 { margin: 0 0 .25rem; font-size: 1.4rem; }
  .sub { color: #888; margin-bottom: 1.5rem; font-size: .9rem; }
  h2 { margin: 1.5rem 0 .5rem; font-size: 1rem; color: #4a90d9; text-transform: uppercase; letter-spacing: .05em; }
  table { border-collapse: collapse; width: 100%; font-size: .9rem; }
  th, td { text-align: left; padding: .5rem .75rem; border-bottom: 1px solid #333; }
  th { background: #1a1a1a; cursor: pointer; user-select: none; position: sticky; top: 0; }
  th:hover { background: #2a2a2a; }
  th.sort-asc::after { content: ' ▲'; color: #4a90d9; }
  th.sort-desc::after { content: ' ▼'; color: #4a90d9; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.poem { cursor: pointer; }
  tr.poem:hover td { background: #1f2a3a; }
  tr.poem.active td { background: #2a3a4a; }
  .name { font-weight: 600; }
  .nr { color: #888; }
  .rank { display: inline-block; width: 1.5em; color: #4a90d9; font-weight: bold; }
  .bar { display: inline-block; height: .6rem; background: linear-gradient(90deg, #4a90d9, #7bb6ee); border-radius: 3px; vertical-align: middle; margin-right: .4rem; }
  #comments { margin-top: 2rem; padding: 1rem; background: #1a1a1a; border-radius: 8px; min-height: 4rem; }
  #comments.empty { color: #666; font-style: italic; padding: 2rem; text-align: center; }
  .comment { padding: .75rem 0; border-bottom: 1px solid #333; }
  .comment:last-child { border-bottom: none; }
  .comment-head { display: flex; gap: .75rem; align-items: baseline; font-size: .85rem; color: #aaa; margin-bottom: .25rem; }
  .comment-head .reader { color: #fff; font-weight: 600; }
  .comment-head .score { color: #4a90d9; font-weight: bold; font-variant-numeric: tabular-nums; }
  .comment-head .img { color: #666; font-family: monospace; font-size: .75rem; }
  .comment-body { font-size: .95rem; line-height: 1.4; }
  .minne { color: #888; font-style: italic; }
  .info { font-size: .8rem; color: #777; margin-top: 1rem; line-height: 1.5; }
</style>
</head>
<body>
<h1>Dikt-dashboard</h1>
<div class="sub">Sammanställning av <strong>__N_FORMS__</strong> kompletta formulär. Klicka på en kolumnrubrik för att sortera. Klicka på en dikt för att se alla kommentarer.</div>

<h2>Översikt — alla dikter</h2>
<table id="main-table">
  <thead><tr>
    <th data-key="nr" class="num">#</th>
    <th data-key="namn">Dikt</th>
    <th data-key="antal" class="num">N</th>
    <th data-key="snitt" class="num" data-default="desc">Snitt</th>
    <th data-key="stddev" class="num">Std.avv.</th>
    <th data-key="total" class="num">Total</th>
    <th data-key="norm_snitt" class="num">Norm. snitt</th>
    <th data-key="norm_stddev" class="num">Norm. std.avv.</th>
    <th data-key="norm_total" class="num">Norm. total</th>
    <th data-key="favoriter" class="num" title="Antal formulär där dikten fick högsta poängen (delade förstaplatser räknas)">★ Favorit</th>
    <th data-key="samst" class="num" title="Antal formulär där dikten fick lägsta poängen (delade sistaplatser räknas)">▼ Sämst</th>
    <th data-key="rank_total" class="num">Rang (total)</th>
    <th data-key="rank_norm" class="num">Rang (norm.)</th>
  </tr></thead>
  <tbody></tbody>
</table>

<div class="info">
  <strong>Snitt/Std.avv./Total:</strong> baserat på den officiella poängen (1–5) per röst.<br>
  <strong>Normaliserad:</strong> i varje formulär ersätts poängen med diktens placering 1–8 (1 = bäst, lika poäng → medelplacering). Lägre värde är bättre.<br>
  <strong>★ Favorit / ▼ Sämst:</strong> antal formulär där dikten fick formulärets högsta respektive lägsta poäng. Vid delade poäng räknas alla på den platsen.
</div>

<h2 id="comment-header">Kommentarer</h2>
<div id="comments" class="empty">Klicka på en dikt ovan för att se kommentarerna.</div>

<script>
const ROWS = __ROWS__;

// Compute ranks (1 = best). Total: highest is best. Norm: lowest is best.
function computeRanks() {
  const byTotal = [...ROWS].sort((a, b) => b.total - a.total);
  byTotal.forEach((r, i) => r.rank_total = i + 1);
  const byNorm = [...ROWS].sort((a, b) => a.norm_snitt - b.norm_snitt);
  byNorm.forEach((r, i) => r.rank_norm = i + 1);
}
computeRanks();

let sortKey = 'snitt';
let sortDir = -1; // -1 desc, +1 asc

function fmt(v, decimals = 2) {
  if (v === null || v === undefined || v === '') return '';
  if (typeof v === 'number') return v.toFixed(decimals);
  return v;
}

function render() {
  const tbody = document.querySelector('#main-table tbody');
  const sorted = [...ROWS].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey];
    if (typeof av === 'string') return sortDir * av.localeCompare(bv, 'sv');
    return sortDir * ((av ?? 0) - (bv ?? 0));
  });
  tbody.innerHTML = sorted.map(r => `
    <tr class="poem" data-nr="${r.nr}">
      <td class="num nr">${r.nr}</td>
      <td class="name">${escapeHtml(r.namn)}</td>
      <td class="num">${r.antal}</td>
      <td class="num">${fmt(r.snitt)}</td>
      <td class="num">${fmt(r.stddev)}</td>
      <td class="num">${fmt(r.total, 1)}</td>
      <td class="num">${fmt(r.norm_snitt)}</td>
      <td class="num">${fmt(r.norm_stddev)}</td>
      <td class="num">${fmt(r.norm_total, 1)}</td>
      <td class="num">${r.favoriter}</td>
      <td class="num">${r.samst}</td>
      <td class="num"><span class="rank">${r.rank_total}</span></td>
      <td class="num"><span class="rank">${r.rank_norm}</span></td>
    </tr>
  `).join('');
  document.querySelectorAll('th').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.key === sortKey) th.classList.add(sortDir < 0 ? 'sort-desc' : 'sort-asc');
  });
  document.querySelectorAll('tr.poem').forEach(tr => {
    tr.addEventListener('click', () => showComments(tr.dataset.nr));
  });
}

function showComments(nr) {
  document.querySelectorAll('tr.poem').forEach(tr => tr.classList.toggle('active', tr.dataset.nr === nr));
  const row = ROWS.find(r => r.nr === nr);
  const div = document.getElementById('comments');
  document.getElementById('comment-header').textContent = `Kommentarer — ${nr}. ${row.namn} (${row.kommentarer.length} st)`;
  if (row.kommentarer.length === 0) {
    div.className = 'empty';
    div.textContent = 'Inga kommentarer eller minnesanteckningar för denna dikt.';
    return;
  }
  div.className = '';
  div.innerHTML = row.kommentarer.map(c => `
    <div class="comment">
      <div class="comment-head">
        <span class="reader">${escapeHtml(c.lasare || '(okänd läsare)')}</span>
        <span class="score">${c.poang.toFixed(1)} p</span>
        <span class="img">${escapeHtml(c.bild)}</span>
      </div>
      <div class="comment-body">
        ${c.minnesanteckning ? `<div class="minne">Minne: ${escapeHtml(c.minnesanteckning)}</div>` : ''}
        ${c.kommentar ? `<div>${escapeHtml(c.kommentar)}</div>` : ''}
      </div>
    </div>
  `).join('');
  document.getElementById('comment-header').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

document.querySelectorAll('th').forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.key;
    if (sortKey === key) sortDir = -sortDir;
    else { sortKey = key; sortDir = th.dataset.default === 'asc' ? 1 : -1; }
    render();
  });
});

render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
