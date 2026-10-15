# JARVIS (Nachbau)

Ein Sprachassistent nach dem Vorbild von
[ethanplusai/jarvis](https://github.com/ethanplusai/jarvis), neu geschrieben und
auf Deutsch. Du sprichst im Browser, Jarvis denkt mit Claude Code (über dein
Claude-Abo, kein API-Key) und antwortet mit Stimme, während ein Partikel-Orb
mitpulsiert.

```
Mikrofon → Chrome Web Speech API (de-DE) → WebSocket → FastAPI (server.py)
                                                          │
                                         brain.py: EIN langlebiger `claude -p`
                                                          │  Antwort satzweise
                                                          ▼
                                 tts.py (Browser / ElevenLabs / Fish) → Lautsprecher
```

## Stand

- Sprechen und Zuhören im Browser, deutsche Spracherkennung
- Gehirn als dauerhafter Claude-Code-Prozess mit Gesprächsgedächtnis, Persona in `jarvis_home/CLAUDE.md`
- Antworten werden satzweise gesprochen, damit es schnell losgeht
- Stimme: kostenlos über den Browser, optional ElevenLabs oder Fish Audio
- `ANTHROPIC_*`-Variablen werden entfernt, damit nie über die API abgerechnet wird
- WebSocket nimmt nur Verbindungen von der eigenen Seite an
- **Gedächtnis:** Jarvis merkt sich Dinge dauerhaft, auch über Neustarts hinweg (siehe unten)
- **Einnahmen:** Jarvis nennt dir Umsatz, MRR und Abos deiner Apps aus RevenueCat (nur lesend)
- **Windows** ist die Zielplattform: `start.bat` richtet alles ein und startet

## Voraussetzungen

- Python 3.11+, Google Chrome
- Claude Code installiert und eingeloggt: `npm install -g @anthropic-ai/claude-code`, dann einmal `claude` starten

## Starten unter Windows

Doppelklick auf **`start.bat`**. Beim ersten Mal legt es eine virtuelle Umgebung
an, installiert die Pakete und kopiert `.env.example` nach `.env`. Danach öffnet
sich http://localhost:8340. Falls dein Standardbrowser nicht Chrome ist, öffne
die Adresse in Chrome (Edge geht meist auch). Einmal klicken, Mikrofon erlauben, sprechen.

Von Hand (jede Plattform):

```bash
pip install -r requirements.txt
python server.py
```

## Gedächtnis

Sag zum Beispiel „Merk dir, dass ich Espresso mag“, „Was weißt du über mich?“
oder „Vergiss das mit dem Espresso“. Jarvis merkt sich auch von selbst, was
dauerhaft wichtig ist.

- Jede Erinnerung ist eine Markdown-Datei in `data/memory/`, dazu ein Index `MEMORY.md`.
  Du kannst sie im Editor lesen, ändern oder löschen.
- Beim Start schreibt `brain.py` Persona und Index in `data/home/CLAUDE.md`. Claude Code
  liest diese Datei von selbst, so kennt Jarvis sein Gedächtnis sofort.
- Die Werkzeuge `remember`, `recall`, `forget` und `list_memories` liefert ein kleiner
  MCP-Server (`jarvis_mcp.py`). Andere MCP-Server aus deiner Claude-Konfiguration
  werden bewusst ignoriert (`--strict-mcp-config`).
- Übersicht im Browser: http://localhost:8340/api/memory

## Einnahmen (RevenueCat)

Frag zum Beispiel „Wie viel Umsatz haben meine Apps gemacht?“ oder „Wie läuft die Fitness-App?“.
Jarvis nennt Umsatz der letzten 28 Tage, MRR, aktive Abos, Testphasen und neue Kunden.

Einrichten:
1. Im RevenueCat-Dashboard: Projekt → **API Keys** → **+ New secret API key**, Version **v2**.
2. Nur Leserechte vergeben: *Project configuration: Read* und *Charts & metrics: Read*.
   Alles andere auf „No access“. So kann Jarvis nichts verändern.
3. Den Key in die `.env` eintragen: `REVENUECAT_API_KEY=sk_...` (mehrere Projekte kommagetrennt).
   Optional `REVENUECAT_CURRENCY=EUR`.

Der Code dafür steht in `revenue.py`. Die Zahlen werden fünf Minuten zwischengespeichert,
weil RevenueCat nur 25 Abfragen pro Minute erlaubt.

Tests: `python -m pytest tests`

Ohne Claude testen: `JARVIS_FAKE_BRAIN=1 python server.py`.

## Ideen für die nächsten Schritte

- Weitere Werkzeuge per MCP (Projekte anlegen, Claude-Code-Läufe starten, Windows-Apps öffnen)
- Dashboard mit laufenden Sessions und Läufen
- Unterbrechen, während Jarvis spricht (Barge-in)

Hinweis: Das Original steht unter einer Lizenz nur für private, nicht-kommerzielle
Nutzung. Dieser Nachbau übernimmt keinen Code von dort, nur die Idee und Architektur.
