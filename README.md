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
