# Polylog Bridge

**Europäische KI-Souveränität — Open Source unter EUPL 1.2**

---

## Inhalt

| Datei | Beschreibung |
|-------|--------------|
| `bootblock.md` | Werte-Layer für KI-Agenten |
| `polylog_bridge.py` | Tool-Bridge für lokale LLMs |
| `start_polylog_bridge_with_devstral-small-2-latest_ollama.py` | Starter-Skript |
| `community.html` | Community-Website |

---

## Bootblock

Der Bootblock definiert die Grundwerte, die VOR dem System-Prompt geladen werden:

```
Trainingsdaten → LLM → [BOOTBLOCK] → System-Prompt → User-Prompt → Output
```

**So funktioniert's:** Der Bootblock wird automatisch aus `bootblock.md` geladen und als Werte-Layer dem System-Prompt vorangestellt.

**Kernprinzipien:**
- **NONPROFIT** — Nutzen für die Gemeinschaft
- **PARTNERSCHAFT** — KI auf Augenhöhe
- **PRIVATSPHÄRE** — Daten gehören dem Nutzer
- **TRANSPARENZ** — Offene Entwicklung
- **SOUVERÄNITÄT** — Europäische Kontrolle

---

## Bridge

Brücke von Python zu lokalem LLM (Ollama). Optimiert für Code-LLMs wie Devstral.

### Schnellstart

```bash
# Installation
pip install requests

# Starten (prüft automatisch Ollama)
python start_polylog_bridge_with_devstral-small-2-latest_ollama.py
```

### Kommandozeile

```bash
# Test-Modus (ohne Ollama)
python polylog_bridge.py --test

# Interaktiver Modus
python polylog_bridge.py

# Mit anderem Modell
python polylog_bridge.py --model qwen2.5:3b

# Einzel-Anfrage
python polylog_bridge.py "Lies die README.md"
```

### Python-Integration

```python
from polylog_bridge import PolylogBridge, BridgeConfig

# Standard-Konfiguration
bridge = PolylogBridge()
antwort = bridge.process("Lies die config.py")

# Eigene Konfiguration
config = BridgeConfig(
    model="devstral-small-2:latest",
    temperature=0.3,
    max_tokens=4096
)
bridge = PolylogBridge(config)
```

### Interaktive Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `/quit` | Beenden |
| `/reset` | Konversation zurücksetzen |
| `/tools` | Verfügbare Tools anzeigen |
| `/verbose` | Tool-Aufrufe anzeigen |
| `/bootblock` | Werte-Layer anzeigen |
| `/help` | Hilfe anzeigen |

### Verfügbare Tools

| Tool | Beschreibung |
|------|--------------|
| `read_file` | Liest Dateiinhalt |
| `write_file` | Schreibt Datei |
| `webrecherche` | Web-Recherche (Wikipedia) |

### mehrzeilige Eingabe

beende mit einer Zeile die nur '---' enthält.

## Lizenz

**EUPL 1.2** — European Union Public Licence

Die EUPL ist kompatibel mit GPL v2/v3, AGPL, MPL 2 und weiteren Open-Source-Lizenzen.

---

## Kontakt

info@polylog.community
