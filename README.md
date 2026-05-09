# Poesi

Verktyg för att extrahera dikt-rankingar från fotograferade pappersformulär.

## Användning

1. Lägg alla fotona i `formular/` (mappen är gitignorerad).
   - HEIC från iPhone måste konverteras till JPG först:
     `sips -s format jpeg formular/*.heic --out formular/`
2. Installera och sätt API-nyckel:
   ```
   pip install -r requirements.txt
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Kör:
   ```
   python extract_forms.py formular/
   ```

Resultat hamnar i `results/`:
- `rader.csv` – en rad per dikt, öppna i Excel/Pandas
- `raw.json` – råsvaret per bild (inkl. övrig text på lappen)
- `errors.txt` – ev. bilder som inte kunde tolkas

Skriptet skriver även ut rader med låg confidence (< 0.7) i terminalen så
du vet vilka du bör dubbelkolla mot originalfotot.

## Granska och korrigera

För att gå igenom allt visuellt mot originalfotona innan du gör statistik:

```
python build_review.py formular/
```

Det skapar `results/granska.html`. Öppna den i en webbläsare:
- Varje foto visas bredvid den extraherade datan.
- Gula rader är de Claude var osäker på.
- Klicka på fotot (eller "Rotera 90°") om bilden ligger upp och ner.
- Alla fält är redigerbara – rätta direkt i sidan.
- Tryck **⬇ CSV** eller **⬇ JSON** uppe i högra hörnet för att ladda ner
  en korrigerad version att analysera vidare.
