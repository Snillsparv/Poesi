#!/usr/bin/env python3
"""Bygg en HTML-vy för att granska och korrigera extraherad data mot originalfoton.

Användning:
    python build_review.py formular/

Skapar results/granska.html. Öppna den i webbläsaren – varje foto visas
bredvid den extraherade datan, fälten är redigerbara, och knapparna
"Exportera CSV/JSON" laddar ner en korrigerad version.
"""

import argparse
import json
import os
import sys
from pathlib import Path

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<title>Granska formulär</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #f4f4f4; color: #222; }
  header { position: sticky; top: 0; background: #222; color: white; padding: 10px 20px;
           display: flex; gap: 12px; align-items: center; z-index: 100; }
  header h1 { font-size: 16px; margin: 0; flex: 1; font-weight: normal; }
  header button { padding: 8px 14px; background: #4a8; color: white; border: 0;
                  border-radius: 4px; cursor: pointer; font-size: 14px; }
  header button:hover { background: #5b9; }
  .stats { background: #efe; color: #060; padding: 6px 10px; border-radius: 4px; font-size: 13px; }
  .form-card { display: flex; gap: 20px; background: white; margin: 20px;
               padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .image-col { flex: 0 0 45%; position: sticky; top: 70px; align-self: flex-start;
               max-height: calc(100vh - 90px); display: flex; flex-direction: column; gap: 8px; }
  .image-wrap { flex: 1; overflow: hidden; display: flex; align-items: center; justify-content: center; background: #fafafa; border: 1px solid #eee; }
  .image-wrap img { max-width: 100%; max-height: calc(100vh - 160px); object-fit: contain;
                    cursor: pointer; transition: transform 0.2s; }
  .rotate-btn { padding: 6px 12px; background: #888; color: white; border: 0;
                border-radius: 4px; cursor: pointer; align-self: flex-start; }
  .data-col { flex: 1; min-width: 0; }
  .data-col h2 { font-size: 14px; margin: 0 0 10px; font-family: monospace; color: #555; }
  .ovrig { margin-bottom: 12px; }
  .ovrig label { display: block; font-weight: bold; margin-bottom: 4px; font-size: 13px; }
  textarea, input { font-family: inherit; font-size: 13px; padding: 4px 6px;
                    border: 1px solid #ccc; border-radius: 3px; width: 100%; }
  textarea { resize: vertical; min-height: 36px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 4px; text-align: left; border-bottom: 1px solid #eee; vertical-align: top; }
  th { font-size: 12px; color: #555; font-weight: 600; }
  tr.low-conf td { background: #fff8c8; }
  td.conf { color: #888; font-size: 12px; white-space: nowrap; }
  .col-num { width: 50px; }
  .col-poang { width: 70px; }
  .col-conf { width: 50px; }
</style>
</head>
<body>
<header>
  <h1>Granska formulär</h1>
  <span class="stats" id="stats"></span>
  <button onclick="exportCSV()">⬇ CSV</button>
  <button onclick="exportJSON()">⬇ JSON</button>
</header>
<div id="cards"></div>
<script>
const DATA = __DATA__;
const IMAGE_PREFIX = "__IMAGE_PREFIX__";

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of children) {
    if (c == null) continue;
    e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return e;
}

function field(tag, value, dataset, cls = '') {
  const e = el(tag, { class: cls });
  if (tag === 'input') e.type = 'text';
  e.value = value ?? '';
  Object.assign(e.dataset, dataset);
  return e;
}

function rotateImage(img) {
  const r = (parseInt(img.dataset.rot || '0') + 90) % 360;
  img.dataset.rot = r;
  img.style.transform = `rotate(${r}deg)`;
}

function buildCard(filename, data) {
  const img = el('img', { src: IMAGE_PREFIX + filename, loading: 'lazy', alt: filename });
  img.addEventListener('click', () => rotateImage(img));
  const rotBtn = el('button', { class: 'rotate-btn', onclick: () => rotateImage(img) }, 'Rotera 90°');
  const imageCol = el('div', { class: 'image-col' },
    el('div', { class: 'image-wrap' }, img),
    rotBtn
  );

  const ovrig = field('textarea', data.ovrig_text, { image: filename, fld: 'ovrig_text' });

  const tbody = el('tbody');
  (data.rader || []).forEach((row, idx) => {
    const tr = el('tr');
    if (typeof row.confidence === 'number' && row.confidence < 0.7) tr.className = 'low-conf';
    const ds = { image: filename, idx: String(idx) };
    const poangAlla = Array.isArray(row.poang_alla) ? row.poang_alla.join('|') : (row.poang_alla || '');
    tr.appendChild(el('td', { class: 'col-num' },     field('input',    row.diktnummer,        { ...ds, fld: 'diktnummer' })));
    tr.appendChild(el('td', {},                       field('textarea', row.minnesanteckning,  { ...ds, fld: 'minnesanteckning' })));
    tr.appendChild(el('td', { class: 'col-poang' },   field('input',    row.poang_officiell,   { ...ds, fld: 'poang_officiell' })));
    tr.appendChild(el('td', { class: 'col-poang' },   field('input',    poangAlla,             { ...ds, fld: 'poang_alla' })));
    tr.appendChild(el('td', {},                       field('textarea', row.kommentar,         { ...ds, fld: 'kommentar' })));
    tr.appendChild(el('td', { class: 'conf col-conf' }, row.confidence != null ? String(row.confidence) : ''));
    tbody.appendChild(tr);
  });

  const table = el('table', {},
    el('thead', {}, el('tr', {},
      el('th', {}, 'Dikt'),
      el('th', {}, 'Minnesanteckning'),
      el('th', {}, 'Poäng (off.)'),
      el('th', {}, 'Poäng (alla)'),
      el('th', {}, 'Kommentar'),
      el('th', {}, 'Conf'),
    )),
    tbody
  );

  const dataCol = el('div', { class: 'data-col' },
    el('h2', {}, filename),
    el('div', { class: 'ovrig' },
      el('label', {}, 'Övrig text på lappen'),
      ovrig
    ),
    table
  );

  return el('section', { class: 'form-card' }, imageCol, dataCol);
}

function readCurrent() {
  const result = {};
  for (const [filename, data] of Object.entries(DATA)) {
    result[filename] = {
      ovrig_text: data.ovrig_text,
      rader: (data.rader || []).map(r => ({ ...r })),
    };
  }
  document.querySelectorAll('input, textarea').forEach(i => {
    const file = i.dataset.image;
    const fld = i.dataset.fld;
    const idx = i.dataset.idx;
    if (!file || !fld) return;
    if (idx !== undefined) {
      const row = result[file].rader[parseInt(idx)];
      if (fld === 'poang_alla') {
        row[fld] = i.value ? i.value.split('|').map(s => s.trim()).filter(Boolean) : [];
      } else {
        row[fld] = i.value || null;
      }
    } else {
      result[file][fld] = i.value || null;
    }
  });
  return result;
}

function exportJSON() {
  const data = readCurrent();
  download('granska_korrigerad.json', JSON.stringify(data, null, 2), 'application/json');
}

function exportCSV() {
  const data = readCurrent();
  const fields = ['bild', 'diktnummer', 'minnesanteckning', 'poang_officiell', 'poang_alla', 'kommentar', 'confidence', 'ovrig_text'];
  const lines = [fields.join(',')];
  for (const [filename, d] of Object.entries(data)) {
    const ovrig = d.ovrig_text || '';
    for (const r of d.rader) {
      const row = [
        filename,
        r.diktnummer || '',
        r.minnesanteckning || '',
        r.poang_officiell || '',
        (r.poang_alla || []).join('|'),
        r.kommentar || '',
        r.confidence != null ? r.confidence : '',
        ovrig,
      ];
      lines.push(row.map(csvEscape).join(','));
    }
  }
  download('granska_korrigerad.csv', '﻿' + lines.join('\n'), 'text/csv;charset=utf-8');
}

function csvEscape(v) {
  v = String(v ?? '');
  if (/[,"\n\r]/.test(v)) return '"' + v.replace(/"/g, '""') + '"';
  return v;
}

function download(name, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const container = document.getElementById('cards');
for (const [filename, data] of Object.entries(DATA)) {
  container.appendChild(buildCard(filename, data));
}
const totalImages = Object.keys(DATA).length;
const totalRows = Object.values(DATA).reduce((n, d) => n + (d.rader || []).length, 0);
const lowConf = Object.values(DATA).reduce((n, d) =>
  n + (d.rader || []).filter(r => typeof r.confidence === 'number' && r.confidence < 0.7).length, 0);
document.getElementById('stats').textContent =
  `${totalImages} bilder · ${totalRows} rader · ${lowConf} osäkra (gula)`;
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, help="Mapp med originalfoton (t.ex. formular/)")
    parser.add_argument("--results", type=Path, default=Path("results"), help="Resultatmapp")
    args = parser.parse_args()

    raw_path = args.results / "raw.json"
    if not raw_path.exists():
        sys.exit(f"Hittade inte {raw_path}. Kör extract_forms.py först.")

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw_sorted = dict(sorted(raw.items()))

    out_path = args.results / "granska.html"
    image_prefix = os.path.relpath(args.folder, start=args.results).replace(os.sep, "/") + "/"

    html = (HTML_TEMPLATE
            .replace("__DATA__", json.dumps(raw_sorted, ensure_ascii=False))
            .replace("__IMAGE_PREFIX__", image_prefix))
    out_path.write_text(html, encoding="utf-8")
    print(f"Skrev {out_path}")
    print(f"Öppna med:  open {out_path}    (eller dra in den i webbläsaren)")


if __name__ == "__main__":
    main()
