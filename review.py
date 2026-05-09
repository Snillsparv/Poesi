#!/usr/bin/env python3
"""Generera en HTML-vy där tolkat resultat visas bredvid originalbilden.

Användning:
    python review.py formular/
    # öppna sedan results/review.html i webbläsaren
"""

import argparse
import json
import os
import sys
from pathlib import Path


HTML_TEMPLATE = """<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<title>Diktformulär – granskning</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 1rem; background: #111; color: #eee; }
  header { position: sticky; top: 0; background: #111; padding: .5rem 0 1rem; border-bottom: 1px solid #333; z-index: 10; }
  h1 { margin: 0 0 .5rem; font-size: 1.2rem; }
  .controls { display: flex; gap: 1rem; align-items: center; font-size: .9rem; }
  .card { display: grid; grid-template-columns: minmax(300px, 45%) 1fr; gap: 1rem; margin: 1.5rem 0; padding: 1rem; background: #1a1a1a; border-radius: 8px; }
  .card h2 { margin: 0 0 .5rem; font-size: 1rem; font-family: monospace; }
  .img-wrap { position: relative; overflow: hidden; border-radius: 4px; background: #000; width: 100%; }
  .img-wrap img { display: block; width: 100%; height: auto; cursor: zoom-in; transform-origin: center center; transition: transform .2s; }
  .rotate-btn { position: absolute; top: .5rem; right: .5rem; background: rgba(0,0,0,.65); color: #fff; border: 1px solid #555; border-radius: 4px; padding: .3rem .6rem; cursor: pointer; font-size: .85rem; z-index: 2; }
  .rotate-btn:hover { background: rgba(0,0,0,.85); }
  table { border-collapse: collapse; width: 100%; font-size: .85rem; }
  th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid #333; vertical-align: top; }
  th { background: #222; position: sticky; top: 0; }
  tr.low-conf td { background: #3a2a1a; }
  tr.med-conf td { background: #2a2a1a; }
  .conf { font-variant-numeric: tabular-nums; }
  .ovrig { margin-top: .75rem; font-size: .85rem; color: #aaa; font-style: italic; }
  [contenteditable] { outline: none; min-width: 1ch; }
  [contenteditable]:hover { background: #2a2a2a; }
  [contenteditable]:focus { background: #1a2a3a; box-shadow: inset 0 0 0 1px #4a90d9; }
  td.edited, .ovrig.edited span[contenteditable] { border-left: 2px solid #4a90d9; padding-left: 4px; }
  td.edited::after { content: ' ✎'; color: #4a90d9; font-size: .7rem; }
  button.action { background: #2a4a6a; color: #fff; border: 1px solid #4a90d9; border-radius: 4px; padding: .35rem .8rem; cursor: pointer; font-size: .85rem; }
  button.action:hover { background: #3a5a7a; }
  button.action.danger { background: #6a2a2a; border-color: #d94a4a; }
  button.action.danger:hover { background: #7a3a3a; }
  #edit-count { color: #4a90d9; font-weight: bold; }
  .hidden { display: none; }
  details summary { cursor: pointer; color: #888; font-size: .8rem; }
  details pre { font-size: .75rem; overflow-x: auto; background: #0a0a0a; padding: .5rem; border-radius: 4px; }
  @media (max-width: 800px) { .card { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>Diktformulär – granskning (__COUNT__ bilder, __ROWS__ rader)</h1>
  <div class="controls">
    <label><input type="checkbox" id="only-low"> Visa bara osäkra rader (conf &lt; 0.7)</label>
    <label>Tröskel: <input type="number" id="threshold" value="0.7" step="0.05" min="0" max="1" style="width: 4rem"></label>
    <span><span id="edit-count">0</span> redigeringar</span>
    <button class="action" id="dl-csv">Ladda ner CSV</button>
    <button class="action" id="dl-json">Ladda ner JSON</button>
    <button class="action danger" id="reset-edits">Återställ ändringar</button>
  </div>
</header>
<main id="cards"></main>
<script>
const DATA = __DATA__;
const IMG_PREFIX = __IMG_PREFIX__;

function classifyConf(c, threshold) {
  if (typeof c !== 'number') return '';
  if (c < threshold - 0.15) return 'low-conf';
  if (c < threshold) return 'med-conf';
  return '';
}

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

const EDIT_FIELDS = ['diktnummer', 'minnesanteckning', 'poang_officiell', 'poang_alla', 'kommentar'];

function loadEdits() {
  try { return JSON.parse(localStorage.getItem('edits') || '{}'); } catch { return {}; }
}
function saveEdits(edits) { localStorage.setItem('edits', JSON.stringify(edits)); }

function getEditedRow(imgName, rowIdx) {
  const edits = loadEdits();
  return (edits[imgName]?.rader?.[rowIdx]) || {};
}
function getEditedOvrig(imgName) {
  const edits = loadEdits();
  return edits[imgName]?.ovrig_text;
}

function setEdit(imgName, rowIdx, field, value, original) {
  const edits = loadEdits();
  edits[imgName] = edits[imgName] || { rader: {} };
  edits[imgName].rader = edits[imgName].rader || {};
  if (value === original || value === '' && (original === null || original === undefined)) {
    if (edits[imgName].rader[rowIdx]) {
      delete edits[imgName].rader[rowIdx][field];
      if (Object.keys(edits[imgName].rader[rowIdx]).length === 0) delete edits[imgName].rader[rowIdx];
    }
  } else {
    edits[imgName].rader[rowIdx] = edits[imgName].rader[rowIdx] || {};
    edits[imgName].rader[rowIdx][field] = value;
  }
  pruneEmpty(edits, imgName);
  saveEdits(edits);
  updateEditCount();
}
function setOvrigEdit(imgName, value, original) {
  const edits = loadEdits();
  edits[imgName] = edits[imgName] || {};
  if (value === (original || '')) delete edits[imgName].ovrig_text;
  else edits[imgName].ovrig_text = value;
  pruneEmpty(edits, imgName);
  saveEdits(edits);
  updateEditCount();
}
function pruneEmpty(edits, imgName) {
  const e = edits[imgName];
  if (!e) return;
  const noRader = !e.rader || Object.keys(e.rader).length === 0;
  const noOvrig = !('ovrig_text' in e);
  if (noRader && noOvrig) delete edits[imgName];
}

function countEdits() {
  const edits = loadEdits();
  let n = 0;
  for (const e of Object.values(edits)) {
    if ('ovrig_text' in e) n++;
    if (e.rader) for (const r of Object.values(e.rader)) n += Object.keys(r).length;
  }
  return n;
}
function updateEditCount() {
  document.getElementById('edit-count').textContent = countEdits();
}

function effectiveValue(original, edited, field) {
  if (edited && field in edited) {
    if (field === 'poang_alla') {
      return edited[field].split('→').map(s => s.trim()).filter(Boolean);
    }
    return edited[field];
  }
  return original[field];
}
function mergedData() {
  const edits = loadEdits();
  const out = {};
  for (const [imgName, data] of Object.entries(DATA)) {
    const e = edits[imgName] || {};
    const merged = { ...data };
    if ('ovrig_text' in e) merged.ovrig_text = e.ovrig_text;
    merged.rader = (data.rader || []).map((row, idx) => {
      const re = e.rader?.[idx];
      if (!re) return row;
      const r = { ...row };
      for (const f of EDIT_FIELDS) {
        if (f in re) {
          if (f === 'poang_alla') r[f] = re[f].split('→').map(s => s.trim()).filter(Boolean);
          else r[f] = re[f];
        }
      }
      return r;
    });
    out[imgName] = merged;
  }
  return out;
}

function render() {
  const onlyLow = document.getElementById('only-low').checked;
  const threshold = parseFloat(document.getElementById('threshold').value) || 0.7;
  const cards = document.getElementById('cards');
  cards.innerHTML = '';
  for (const [imgName, data] of Object.entries(DATA)) {
    const rows = data.rader || [];
    const visibleRows = onlyLow
      ? rows.map((r, i) => [r, i]).filter(([r]) => typeof r.confidence === 'number' && r.confidence < threshold)
      : rows.map((r, i) => [r, i]);
    if (onlyLow && visibleRows.length === 0) continue;
    const card = document.createElement('section');
    card.className = 'card';
    const imgPath = IMG_PREFIX + encodeURIComponent(imgName);
    const stored = localStorage.getItem('rot:' + imgName);
    const rot = stored !== null ? parseInt(stored) : 270;
    const ovrigEdited = getEditedOvrig(imgName);
    const ovrigValue = ovrigEdited !== undefined ? ovrigEdited : (data.ovrig_text || '');
    const ovrigIsEdited = ovrigEdited !== undefined;
    card.innerHTML = `
      <div>
        <h2>${escapeHtml(imgName)}</h2>
        <div class="img-wrap" data-rot="${rot}" data-name="${escapeHtml(imgName)}">
          <button class="rotate-btn" title="Rotera 90°">↻</button>
          <a href="${imgPath}" target="_blank"><img src="${imgPath}" loading="lazy" alt=""></a>
        </div>
      </div>
      <div>
        <table>
          <thead><tr>
            <th>#</th><th>Minnesanteckning</th><th>Poäng</th><th>Alla</th><th>Kommentar</th><th>Conf</th>
          </tr></thead>
          <tbody>
            ${visibleRows.map(([r, idx]) => {
              const ed = getEditedRow(imgName, idx);
              const cell = (field, content) => {
                const isEdited = field in ed;
                const cls = isEdited ? 'edited' : '';
                return `<td class="${cls}" contenteditable="true" data-img="${escapeHtml(imgName)}" data-row="${idx}" data-field="${field}">${content}</td>`;
              };
              const v = (f) => effectiveValue(r, ed, f);
              return `
              <tr class="${classifyConf(r.confidence, threshold)}">
                ${cell('diktnummer', escapeHtml(v('diktnummer')))}
                ${cell('minnesanteckning', escapeHtml(v('minnesanteckning')))}
                ${cell('poang_officiell', escapeHtml(v('poang_officiell')))}
                ${cell('poang_alla', escapeHtml((v('poang_alla') || []).join(' → ')))}
                ${cell('kommentar', escapeHtml(v('kommentar')))}
                <td class="conf">${typeof r.confidence === 'number' ? r.confidence.toFixed(2) : ''}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
        <div class="ovrig ${ovrigIsEdited ? 'edited' : ''}">Övrig text: <span contenteditable="true" data-img="${escapeHtml(imgName)}" data-field="ovrig_text">${escapeHtml(ovrigValue)}</span></div>
        <details><summary>JSON</summary><pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre></details>
      </div>
    `;
    cards.appendChild(card);
  }
  document.querySelectorAll('.img-wrap').forEach(setupWrap);
  bindEditableCells();
  updateEditCount();
}

function bindEditableCells() {
  document.querySelectorAll('td[contenteditable]').forEach(td => {
    if (td.dataset.bound) return;
    td.dataset.bound = '1';
    td.addEventListener('blur', () => {
      const imgName = td.dataset.img;
      const idx = parseInt(td.dataset.row);
      const field = td.dataset.field;
      const value = td.textContent.trim();
      const original = DATA[imgName].rader[idx][field];
      const origStr = field === 'poang_alla' ? (original || []).join(' → ') : (original ?? '');
      setEdit(imgName, idx, field, value, origStr);
      td.classList.toggle('edited', value !== origStr);
    });
    td.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); td.blur(); }
      if (e.key === 'Escape') { e.preventDefault(); td.blur(); }
    });
  });
  document.querySelectorAll('.ovrig span[contenteditable]').forEach(span => {
    if (span.dataset.bound) return;
    span.dataset.bound = '1';
    span.addEventListener('blur', () => {
      const imgName = span.dataset.img;
      const value = span.textContent.trim();
      const original = DATA[imgName].ovrig_text || '';
      setOvrigEdit(imgName, value, original);
      span.parentElement.classList.toggle('edited', value !== original);
    });
    span.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); span.blur(); }
    });
  });
}

function csvEscape(s) {
  if (s === null || s === undefined) return '';
  s = String(s);
  if (/[",\\n\\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}
function buildCsv() {
  const merged = mergedData();
  const fields = ['bild','diktnummer','minnesanteckning','poang_officiell','poang_alla','kommentar','confidence','ovrig_text'];
  const lines = [fields.join(',')];
  for (const [imgName, data] of Object.entries(merged)) {
    const ovrig = data.ovrig_text || '';
    for (const r of (data.rader || [])) {
      lines.push([
        csvEscape(imgName),
        csvEscape(r.diktnummer ?? ''),
        csvEscape(r.minnesanteckning ?? ''),
        csvEscape(r.poang_officiell ?? ''),
        csvEscape((r.poang_alla || []).join('|')),
        csvEscape(r.kommentar ?? ''),
        csvEscape(typeof r.confidence === 'number' ? r.confidence : ''),
        csvEscape(ovrig),
      ].join(','));
    }
  }
  return '﻿' + lines.join('\\r\\n');
}
function download(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 0);
}

function applyRotation(wrap) {
  const rot = parseInt(wrap.dataset.rot) || 0;
  const img = wrap.querySelector('img');
  if (!img.complete || !img.naturalWidth) {
    img.addEventListener('load', () => applyRotation(wrap), { once: true });
    return;
  }
  const swapped = rot === 90 || rot === 270;
  const wrapW = wrap.clientWidth;
  if (swapped) {
    const scale = wrapW / img.naturalHeight;
    const displayedH = img.naturalWidth * scale;
    wrap.style.height = displayedH + 'px';
    img.style.position = 'absolute';
    img.style.left = '50%';
    img.style.top = '50%';
    img.style.width = img.naturalWidth + 'px';
    img.style.height = img.naturalHeight + 'px';
    img.style.transform = `translate(-50%, -50%) rotate(${rot}deg) scale(${scale})`;
  } else {
    wrap.style.height = '';
    img.style.position = '';
    img.style.left = '';
    img.style.top = '';
    img.style.width = '';
    img.style.height = '';
    img.style.transform = rot ? `rotate(${rot}deg)` : '';
  }
}

function setupWrap(wrap) {
  applyRotation(wrap);
  const btn = wrap.querySelector('.rotate-btn');
  if (btn.dataset.bound) return;
  btn.dataset.bound = '1';
  btn.addEventListener('click', e => {
    e.preventDefault();
    e.stopPropagation();
    const next = ((parseInt(wrap.dataset.rot) || 0) + 90) % 360;
    wrap.dataset.rot = next;
    localStorage.setItem('rot:' + wrap.dataset.name, next);
    applyRotation(wrap);
  });
}

window.addEventListener('resize', () => {
  document.querySelectorAll('.img-wrap').forEach(applyRotation);
});

document.getElementById('only-low').addEventListener('change', render);
document.getElementById('threshold').addEventListener('input', render);
document.getElementById('dl-csv').addEventListener('click', () => {
  download('rader_korrigerad.csv', buildCsv(), 'text/csv;charset=utf-8');
});
document.getElementById('dl-json').addEventListener('click', () => {
  download('raw_korrigerad.json', JSON.stringify(mergedData(), null, 2), 'application/json;charset=utf-8');
});
document.getElementById('reset-edits').addEventListener('click', () => {
  if (!confirm('Återställ alla redigeringar? Detta går inte att ångra.')) return;
  localStorage.removeItem('edits');
  render();
});
render();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, help="Mapp med originalbilderna")
    parser.add_argument("--results", type=Path, default=Path("results"), help="Resultatmapp (default: results)")
    parser.add_argument("--out", type=Path, default=None, help="Sökväg till HTML-filen (default: <results>/review.html)")
    args = parser.parse_args()

    raw_path = args.results / "raw.json"
    if not raw_path.is_file():
        sys.exit(f"Hittar inte {raw_path}. Kör extract_forms.py först.")
    if not args.folder.is_dir():
        sys.exit(f"Inte en mapp: {args.folder}")

    data = json.loads(raw_path.read_text(encoding="utf-8"))
    out_path = args.out or (args.results / "review.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rel = os.path.relpath(args.folder.resolve(), out_path.resolve().parent).replace("\\", "/")
    img_prefix = rel + "/"

    total_rows = sum(len(d.get("rader", [])) for d in data.values())
    html = (HTML_TEMPLATE
            .replace("__COUNT__", str(len(data)))
            .replace("__ROWS__", str(total_rows))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__IMG_PREFIX__", json.dumps(img_prefix)))
    out_path.write_text(html, encoding="utf-8")
    print(f"Skrev {out_path}")
    print(f"Öppna den i webbläsaren (t.ex. dubbelklicka, eller: start {out_path})")


if __name__ == "__main__":
    main()
