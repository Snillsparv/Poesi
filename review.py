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

function render() {
  const onlyLow = document.getElementById('only-low').checked;
  const threshold = parseFloat(document.getElementById('threshold').value) || 0.7;
  const cards = document.getElementById('cards');
  cards.innerHTML = '';
  for (const [imgName, data] of Object.entries(DATA)) {
    const rows = data.rader || [];
    const visibleRows = onlyLow
      ? rows.filter(r => typeof r.confidence === 'number' && r.confidence < threshold)
      : rows;
    if (onlyLow && visibleRows.length === 0) continue;
    const card = document.createElement('section');
    card.className = 'card';
    const imgPath = IMG_PREFIX + encodeURIComponent(imgName);
    const rot = parseInt(localStorage.getItem('rot:' + imgName)) || 0;
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
            ${visibleRows.map(r => `
              <tr class="${classifyConf(r.confidence, threshold)}">
                <td>${escapeHtml(r.diktnummer)}</td>
                <td>${escapeHtml(r.minnesanteckning)}</td>
                <td><strong>${escapeHtml(r.poang_officiell)}</strong></td>
                <td>${escapeHtml((r.poang_alla || []).join(' → '))}</td>
                <td>${escapeHtml(r.kommentar)}</td>
                <td class="conf">${typeof r.confidence === 'number' ? r.confidence.toFixed(2) : ''}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        ${data.ovrig_text ? `<div class="ovrig">Övrig text: ${escapeHtml(data.ovrig_text)}</div>` : ''}
        <details><summary>JSON</summary><pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre></details>
      </div>
    `;
    cards.appendChild(card);
  }
  document.querySelectorAll('.img-wrap').forEach(setupWrap);
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
