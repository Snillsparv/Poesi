#!/usr/bin/env python3
"""Extrahera dikt-rankingformulär från foton via Claude.

Användning:
    export ANTHROPIC_API_KEY=sk-ant-...
    python extract_forms.py formular/

Resultat hamnar i ./results/:
    rader.csv     – en rad per dikt-rad i formuläret (öppna i Excel)
    raw.json      – hela råsvaret per bild
    errors.txt    – bilder som misslyckades (om några)

HEIC-bilder från iPhone fungerar inte direkt. Konvertera först:
    sips -s format jpeg formular/*.heic --out formular/
"""

import argparse
import base64
import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-6"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

PROMPT = """Du tittar på ett foto av ett pappersformulär där en person har rankat dikter.

Formuläret har en rad per dikt med kolumnerna:
1. Diktnummer
2. Minnesanteckning – personens egen anteckning om vad dikten handlade om
3. Poäng – ibland står det två poäng (en överstruken/ändrad och en ny). Den SENAST skrivna är officiell. Inkludera båda om så är fallet.
4. Kommentar – fritextkommentar

Det kan också stå övrig text någonstans på lappen (rubrik, namn, datum, kantanteckningar). Ta med det om du hittar det.

Vissa lappar är handskrivna och svårlästa. Gissa hellre än att hoppa över, men sätt en låg confidence (0–1) på rader där du är osäker.

Returnera ENBART giltig JSON, inga kodblock, ingen förklaring. Format:

{
  "ovrig_text": "all övrig text på lappen som inte tillhör en specifik rad, eller null",
  "rader": [
    {
      "diktnummer": "1",
      "minnesanteckning": "...",
      "poang_officiell": "7",
      "poang_alla": ["5", "7"],
      "kommentar": "...",
      "confidence": 0.9
    }
  ]
}

Tomma celler: sätt fältet till null. Om bara en poäng finns: sätt poang_alla till en lista med bara den."""


def encode_image(path: Path) -> tuple[str, str]:
    media_type = MEDIA_TYPES[path.suffix.lower()]
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return media_type, data


def parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rsplit("```", 1)[0].strip()
    return json.loads(text)


def extract_one(client: anthropic.Anthropic, image_path: Path) -> dict:
    media_type, data = encode_image(image_path)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    )
    return parse_json_response(response.content[0].text)


def process_image(client: anthropic.Anthropic, path: Path):
    try:
        return path, extract_one(client, path), None
    except Exception as e:
        return path, None, f"{type(e).__name__}: {e}"


def write_csv(raw_results: dict, csv_path: Path) -> None:
    fields = [
        "bild",
        "diktnummer",
        "minnesanteckning",
        "poang_officiell",
        "poang_alla",
        "kommentar",
        "confidence",
        "ovrig_text",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for image_name, data in raw_results.items():
            ovrig = data.get("ovrig_text") or ""
            for row in data.get("rader", []):
                poang_alla = row.get("poang_alla") or []
                writer.writerow({
                    "bild": image_name,
                    "diktnummer": row.get("diktnummer") or "",
                    "minnesanteckning": row.get("minnesanteckning") or "",
                    "poang_officiell": row.get("poang_officiell") or "",
                    "poang_alla": "|".join(str(p) for p in poang_alla),
                    "kommentar": row.get("kommentar") or "",
                    "confidence": row.get("confidence") if row.get("confidence") is not None else "",
                    "ovrig_text": ovrig,
                })


def report_low_confidence(raw_results: dict, threshold: float = 0.7) -> None:
    flagged = []
    for image_name, data in raw_results.items():
        for row in data.get("rader", []):
            c = row.get("confidence")
            if isinstance(c, (int, float)) and c < threshold:
                flagged.append((image_name, row.get("diktnummer"), c))
    if not flagged:
        return
    print(f"\n{len(flagged)} rader med confidence < {threshold} (granska manuellt):")
    for img, num, c in sorted(flagged, key=lambda x: x[2]):
        print(f"  {img}  dikt {num}  conf={c}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("folder", type=Path, help="Mapp med formulärfoton")
    parser.add_argument("--out", type=Path, default=Path("results"), help="Resultatmapp")
    parser.add_argument("--workers", type=int, default=8, help="Parallella API-anrop")
    args = parser.parse_args()

    if not args.folder.is_dir():
        sys.exit(f"Inte en mapp: {args.folder}")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Sätt miljövariabeln ANTHROPIC_API_KEY först")

    images = sorted(p for p in args.folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    if not images:
        sys.exit(f"Inga bilder hittades i {args.folder}")

    print(f"Bearbetar {len(images)} bilder med {args.workers} parallella anrop...")

    args.out.mkdir(exist_ok=True)
    client = anthropic.Anthropic(api_key=api_key)
    raw_results: dict = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(process_image, client, p) for p in images]
        for i, future in enumerate(as_completed(futures), 1):
            path, result, error = future.result()
            if error:
                print(f"[{i}/{len(images)}] FEL  {path.name}: {error}")
                errors.append(f"{path.name}: {error}")
            else:
                rows = len(result.get("rader", []))
                print(f"[{i}/{len(images)}] OK   {path.name} ({rows} rader)")
                raw_results[path.name] = result

    raw_path = args.out / "raw.json"
    csv_path = args.out / "rader.csv"
    errors_path = args.out / "errors.txt"

    raw_path.write_text(json.dumps(raw_results, ensure_ascii=False, indent=2))
    write_csv(raw_results, csv_path)
    if errors:
        errors_path.write_text("\n".join(errors))

    print(f"\nKlart. Skrev {csv_path} och {raw_path}")
    if errors:
        print(f"{len(errors)} fel listade i {errors_path}")
    report_low_confidence(raw_results)


if __name__ == "__main__":
    main()
