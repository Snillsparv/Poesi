#!/usr/bin/env python3
"""Filtrera bort formulär där någon dikt saknar officiell poäng.

Användning:
    python filter_complete.py [resultatmapp]   # default: results

Läser <mapp>/raw_korrigerad.json och skriver:
    <mapp>/raw_komplett.json   – endast formulär med poäng på alla rader
    <mapp>/rader_komplett.csv  – samma data i CSV
    <mapp>/exkluderade.txt     – lista över borttagna formulär och varför
"""

import csv
import json
import sys
from pathlib import Path


def main() -> None:
    results = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
    src = results / "raw_korrigerad.json"
    if not src.is_file():
        sys.exit(f"Hittar inte {src}")

    data = json.loads(src.read_text(encoding="utf-8"))

    complete: dict = {}
    excluded: list[tuple[str, list[str]]] = []
    for img, entry in data.items():
        rows = entry.get("rader", [])
        missing = [r.get("diktnummer") or "?" for r in rows if not r.get("poang_officiell")]
        if missing or not rows:
            excluded.append((img, missing))
        else:
            complete[img] = entry

    (results / "raw_komplett.json").write_text(
        json.dumps(complete, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fields = [
        "bild", "diktnummer", "minnesanteckning",
        "poang_officiell", "poang_alla", "kommentar", "confidence", "ovrig_text",
    ]
    with (results / "rader_komplett.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for img, entry in complete.items():
            ovrig = entry.get("ovrig_text") or ""
            for r in entry.get("rader", []):
                writer.writerow({
                    "bild": img,
                    "diktnummer": r.get("diktnummer") or "",
                    "minnesanteckning": r.get("minnesanteckning") or "",
                    "poang_officiell": r.get("poang_officiell") or "",
                    "poang_alla": "|".join(str(p) for p in r.get("poang_alla") or []),
                    "kommentar": r.get("kommentar") or "",
                    "confidence": r.get("confidence") if r.get("confidence") is not None else "",
                    "ovrig_text": ovrig,
                })

    lines = [f"Originalfil: {src.name}", f"Behållna: {len(complete)} formulär", f"Exkluderade: {len(excluded)} formulär", ""]
    for img, missing in excluded:
        lines.append(f"{img}: saknar poäng på dikt {', '.join(missing) if missing else '(inga rader)'}")
    (results / "exkluderade.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"Behöll {len(complete)} formulär, exkluderade {len(excluded)}.")
    for img, missing in excluded:
        print(f"  - {img} (saknar dikt {', '.join(missing) if missing else 'allt'})")


if __name__ == "__main__":
    main()
