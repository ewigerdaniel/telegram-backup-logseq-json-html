# Telegram Backup

Dieses Tool sichert Telegram-Chats, Kanäle und Gruppen lokal als JSON, HTML und Logseq-Journal.

## Was es tut

Das Skript verbindet sich über die offizielle Telegram-API mit deinem Account und lädt Nachrichten sowie Medien (Fotos, Sprachnachrichten, Dokumente, Sticker) herunter. Videos und Musik werden nicht heruntergeladen — stattdessen wird ein direkter Telegram-Link gespeichert.

Jeder Backup-Lauf ist **inkrementell**: es werden nur neue Nachrichten seit dem letzten Lauf geholt, nichts wird doppelt gespeichert.

Die gesicherten Daten werden in drei Formaten ausgegeben:
- **JSON** — maschinenlesbare Rohdaten, Basis für alle anderen Formate
- **HTML** — browsbare Ansicht ähnlich dem nativen Telegram-Export, mit klickbaren Links und Medienvorschau
- **Logseq** — Journal-Einträge pro Tag, Teilnehmer als verlinkte Pages; optional direkt in einen bestehenden Logseq-Graphen schreiben

Über `LOGSEQ_JOURNAL_DIR`, `LOGSEQ_PAGES_DIR` und `LOGSEQ_ASSETS_DIR` in `config.py` kann das Tool direkt in einen laufenden Logseq-Graphen schreiben — Nachrichten landen dann sofort im Tagesjournal, Medien im Assets-Ordner. Ohne diese Einstellung werden alle Daten nach `backups/logseq-telegram/` geschrieben, das als eigenständiger Graph geöffnet oder mit `merge_to_logseq.py` in einen bestehenden Graphen übertragen werden kann.


## Ausgabestruktur

```
backups/
├── json/
│   └── 1234567890_Ralf/
│       ├── messages.json          # Alle Nachrichten als JSON (Rohdaten)
│       ├── state.json             # Letzter gesicherter Stand (inkrementell)
│       └── .logseq_manifest.json  # Bereits nach Logseq exportierte Nachrichten-IDs
├── html/
│   └── 1234567890_Ralf/
│       └── index.html             # Browsbare HTML-Ansicht
└── logseq-telegram/               # Kann direkt in Logseq geöffnet werden
    ├── journals/
    │   └── 2024_03_21.md
    ├── pages/
    │   └── Ralf @ralf_tg.md
    └── assets/
        └── 1234567890_Ralf/
            └── media/
                ├── photos/        # Fotos (.jpg)
                ├── voice/         # Sprachnachrichten (.ogg)
                ├── documents/     # Dokumente
                └── stickers/      # Sticker
```

**Wichtig:** Die HTML-Dateien verwenden relative Pfade zu den Medien in `logseq-telegram/assets/`.
`html/` und `logseq-telegram/` müssen daher immer zusammen unter demselben `BACKUP_DIR` liegen.
Werden sie getrennt verschoben, funktionieren Bilder und Sprachnachrichten in der HTML-Ansicht nicht mehr.

---

## Setup

### 1. Virtuelle Umgebung einrichten

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. API-Zugangsdaten holen

1. Auf [my.telegram.org](https://my.telegram.org) anmelden
2. → **API development tools** → App erstellen
3. `api_id` und `api_hash` kopieren

### 3. `.env` anlegen

```bash
cp .env.example .env
nano .env
```

```env
TELEGRAM_API_ID=12345678           # von my.telegram.org
TELEGRAM_API_HASH=abcdef...        # von my.telegram.org
TELEGRAM_PHONE=+49123456789        # deine Telefonnummer mit Ländervorwahl
```

### 4. `config.py` anpassen

```python
BACKUP_DIR = "backups"   # Zielordner für alle Ausgaben (relativ zum Projektordner)

# Optional: Logseq-Pfade direkt auf einen bestehenden Graphen zeigen lassen
# None = Ausgabe nach backups/logseq-telegram/ (Standard)
LOGSEQ_JOURNAL_DIR = None   # z.B. "/home/user/logseq/journals"
LOGSEQ_PAGES_DIR   = None   # z.B. "/home/user/logseq/pages"
LOGSEQ_ASSETS_DIR  = None   # z.B. "/home/user/logseq/assets"
```

### 5. Chats auflisten und IDs in `config.py` eintragen

```bash
python backup.py --list
```

Beim ersten Start fragt Telethon nach dem Bestätigungscode (per SMS oder Telegram-App).
Die Session wird in `session/` gespeichert — danach kein erneuter Login nötig.

---

## Befehle

### Alle konfigurierten Chats sichern

```bash
python backup.py
```

Nutzt die Exportformate aus `config.py` (`EXPORT_FORMATS`).

---

### Nur bestimmte Formate exportieren

```bash
python backup.py --export html
python backup.py --export logseq
python backup.py --export html logseq
```

| Format | Ausgabe |
|--------|---------|
| JSON | `backups/json/{id}_{name}/messages.json` (immer, kein Flag nötig) |
| `html` | `backups/html/{id}_{name}/index.html` |
| `logseq` | `backups/logseq-telegram/` (oder direkt in `LOGSEQ_*`-Pfade wenn gesetzt) |

---

### Verfügbare Chats auflisten

```bash
python backup.py --list
```

```
Verfügbare Chats (ID · Name):
  1234567890  ·  Ralf
  987654321   ·  Familiengruppe  ✓ Whitelist
  111222333   ·  Spam-Kanal      ✗ Blacklist
```

Die IDs werden in `config.py` unter `WHITELIST` / `BLACKLIST` eingetragen.

---

### Logseq neu generieren (nach Ordner-Löschung o.ä.)

```bash
rm backups/json/{id}_{name}/.logseq_manifest.json
python backup.py --export logseq
```

Das Manifest verhindert Duplikate — ohne es werden alle Nachrichten neu exportiert.

---

## Alle Einstellungen auf einen Blick

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `BACKUP_DIR` | `"backups"` | Zielordner für alle Ausgaben |
| `WHITELIST` | `[]` | Nur diese Chat-IDs sichern (leer = alle) |
| `BLACKLIST` | `[]` | Diese Chat-IDs immer überspringen |
| `SKIP_MEDIA_TYPES` | `["video", "audio"]` | Medientypen ohne Download (Telegram-Link statt Datei) |
| `MAX_DOWNLOAD_SIZE_MB` | `1` | Maximale Dateigröße für Downloads in MB (gilt für Dokumente/Audio/Sticker; `None` = kein Limit) |
| `EXPORT_FORMATS` | `["html", "logseq"]` | Aktive Exportformate |
| `LOGSEQ_DATE_FORMAT` | `"%Y_%m_%d"` | Dateinamensformat für Journal-Einträge |
| `LOGSEQ_JOURNAL_DIR` | `None` | Logseq-Journals-Pfad (None = `backups/logseq-telegram/journals`) |
| `LOGSEQ_PAGES_DIR` | `None` | Logseq-Pages-Pfad (None = `backups/logseq-telegram/pages`) |
| `LOGSEQ_ASSETS_DIR` | `None` | Logseq-Assets-Pfad (None = `backups/logseq-telegram/assets`) |

IDs für Whitelist/Blacklist ermitteln: `python backup.py --list`

---

## Konfiguration (`config.py`)

### Chat-Auswahl

IDs werden mit `python backup.py --list` ermittelt.

```python
# Nur diese Chats sichern (leer = alle, minus Blacklist)
WHITELIST: list[int] = [
    1234567890,  # Name des Chats
]

# Diese Chats immer überspringen
BLACKLIST: list[int] = [
    111222333,   # Name des Chats
]
```

**Logik:**
- Blacklist wird immer zuerst geprüft — ein Chat in der Blacklist wird nie gesichert
- Whitelist leer → alle Chats werden gesichert (Blacklist greift)
- Whitelist gefüllt → nur die gelisteten Chats werden gesichert

### Medien

```python
# Für diese Typen wird kein Download durchgeführt.
# Stattdessen wird der Telegram-Link gespeichert.
SKIP_MEDIA_TYPES = ["video", "audio"]
```

| Typ | Standardverhalten | Unterordner |
|-----|-------------------|-------------|
| Fotos | Download | `media/photos/` |
| Sprachnachrichten | Download | `media/voice/` |
| Dokumente / PDFs | Download wenn ≤ `MAX_DOWNLOAD_SIZE_MB` | `media/documents/` |
| Sticker | Download wenn ≤ `MAX_DOWNLOAD_SIZE_MB` | `media/stickers/` |
| Videos | **kein Download** → Telegram-Link | — |
| Musik / Audio | **kein Download** → Telegram-Link | — |

Für nicht heruntergeladene Medien wird der direkte Telegram-Link zur Originalnachricht gespeichert.
Bei weitergeleiteten Nachrichten zeigt der Link auf die Originalquelle.
Für private 1:1-Chats ohne öffentliche URL wird kein Link gespeichert.

**Alles herunterladen (inkl. Videos, ohne Größenlimit):**
```python
SKIP_MEDIA_TYPES = []
MAX_DOWNLOAD_SIZE_MB = None
```

### Exportformate

```python
# Standardmäßig aktive Formate (überschreibbar per --export)
EXPORT_FORMATS = ["html", "logseq"]
```

### Logseq

```python
# Dateinamen-Format für Journal-Einträge (Standard Logseq: %Y_%m_%d)
LOGSEQ_DATE_FORMAT = "%Y_%m_%d"   # → 2024_03_21.md

# Optional: direkt in einen externen Logseq-Graphen schreiben
# None = Standard-Ausgabe nach backups/logseq-telegram/
LOGSEQ_JOURNAL_DIR = None   # z.B. "/absoluter/pfad/logseq/journals"
LOGSEQ_PAGES_DIR   = None   # z.B. "/absoluter/pfad/logseq/pages"
LOGSEQ_ASSETS_DIR  = None   # z.B. "/absoluter/pfad/logseq/assets"
```

---

## Logseq-Integration

Jede Nachricht wird als Block ins Tagesjournal eingetragen:

```markdown
- [[Telegram]] [[Ralf @ralf_tg]] #telegram-backup
  - 14:30 [[Ralf @ralf_tg]]: Hallo!
  - 14:31 [[Ich @mein_username]]: Hi!
    - 🖼 ![](../../assets/1234567890_Ralf/media/photos/12345.jpg)
  - 14:32 [[Ralf @ralf_tg]]: Schau mal das Video
    - 🎥 [Telegram-Link](https://t.me/c/.../12346)
  - 14:33 [[Ralf @ralf_tg]]: Antwort
    - ↩ Antwort auf Nachricht 185078
```

**Seitennamen:** Teilnehmer werden als `Rufname @username` angelegt — Chat-Header und
Sender-Links nutzen dasselbe Format, sodass nur eine Page pro Person entsteht.

Teilnehmer-Pages werden nur neu angelegt, wenn sie noch nicht existieren — bestehende
Pages werden nie überschrieben.

---

## In den Logseq-Hauptgraphen übertragen

Wenn `LOGSEQ_JOURNAL_DIR` / `LOGSEQ_PAGES_DIR` nicht direkt gesetzt sind (Standard),
kann `merge_to_logseq.py` die Daten aus `backups/logseq-telegram/` in einen bestehenden
Graphen übertragen.

```python
# config.py — Ziel-Graph setzen:
LOGSEQ_JOURNAL_DIR = "/pfad/zum/graphen/journals"
LOGSEQ_PAGES_DIR   = "/pfad/zum/graphen/pages"
```

### Vorschau (nichts wird geschrieben)

```bash
python merge_to_logseq.py --dry-run
```

### Übertragen

```bash
python merge_to_logseq.py
```

**Sicherheitsgarantien:**
- Journal-Einträge werden nur **angehängt**, nie überschrieben
- Pages werden nur neu angelegt, wenn sie noch **nicht existieren**
- Bereits übertragene Inhalte werden **nicht doppelt** eingefügt (Manifest in `backups/_merge_manifest.json`)

---

## Tipps

**venv nach Neustart aktivieren:**
```bash
source .venv/bin/activate
```

**Backup automatisch ausführen (Cron-Job):**
```bash
crontab -e
# Täglich um 3 Uhr:
0 3 * * * cd /pfad/zum/projekt && .venv/bin/python backup.py
```
