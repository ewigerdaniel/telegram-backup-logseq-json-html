# Telegram Backup

Sichert Telegram-Chats, Kanäle und Gruppen lokal als JSON, HTML und Logseq-Journal.
Jeder Lauf ist inkrementell — es werden nur neue Nachrichten seit dem letzten Mal geholt.

---

## Voraussetzungen

- Python 3.10 oder neuer
- Ein Telegram-Account (kein Bot — das Tool meldet sich als dein normaler Account an)

---

## Einrichtung (einmalig)

### 1. Virtuelle Umgebung einrichten

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. API-Zugangsdaten bei Telegram holen

1. Im Browser auf [my.telegram.org](https://my.telegram.org) einloggen
2. **API development tools** anklicken
3. Eine App anlegen (Name und Plattform sind egal, z. B. "Backup")
4. `api_id` (Zahl) und `api_hash` (langer String) notieren

### 3. `.env`-Datei anlegen

```bash
cp .env.example .env
```

Die Datei mit einem Texteditor öffnen und ausfüllen:

```env
TELEGRAM_API_ID=12345678           # deine api_id von my.telegram.org
TELEGRAM_API_HASH=abcdef...        # dein api_hash von my.telegram.org
TELEGRAM_PHONE=+49123456789        # deine Telefonnummer mit Ländervorwahl
```

### 4. Chats in `config.py` eintragen

```bash
source .venv/bin/activate   # falls noch nicht aktiv
python setup_whitelist.py
```

Beim allerersten Start meldet sich das Tool bei Telegram an.
Telegram schickt dir einen **Bestätigungscode** per SMS oder in die Telegram-App — einfach ins Terminal eingeben.

Das Skript listet alle verfügbaren Chats auf und trägt sie **kommentiert** in die `WHITELIST` ein:

```python
WHITELIST: list[int] = [
    # 1234567890,  # Ralf
    # 987654321,   # Familiengruppe
    # 111222333,   # Spam-Kanal
]
```

Danach `config.py` öffnen und das `#` vor den Chats entfernen, die gesichert werden sollen.
Leer lassen (alles auskommentiert) bedeutet: alle Chats sichern (außer Blacklist).

Die Session wird in `session/` gespeichert — der Login-Code wird nur beim allerersten Start abgefragt.

---

## Tägliche Nutzung

```bash
source .venv/bin/activate   # venv aktivieren (nach jedem Neustart nötig)
python backup.py            # alle konfigurierten Chats sichern
```

Das war's. Das Tool holt nur neue Nachrichten seit dem letzten Lauf und aktualisiert HTML und Logseq-Journal automatisch.

### Nur bestimmte Formate exportieren

```bash
python backup.py --export html          # nur HTML
python backup.py --export logseq        # nur Logseq
python backup.py --export html logseq   # beide (Standard)
```

JSON wird immer geschrieben — es ist die Datenbasis für alle anderen Formate.

---

## Ausgabestruktur

```
backups/
├── json/
│   └── 1234567890_Ralf/
│       ├── messages.json          # alle Nachrichten als Rohdaten
│       ├── state.json             # Fortschritt (für inkrementelle Backups)
│       └── .logseq_manifest.json  # bereits exportierte Nachrichten-IDs
├── html/
│   └── 1234567890_Ralf/
│       └── index.html             # browsbare Ansicht im Browser
└── logseq-telegram/
    ├── journals/
    │   └── 2024_03_21.md
    ├── pages/
    │   └── Ralf @ralf_tg.md
    └── assets/
        └── 1234567890_Ralf/
            └── media/
                ├── photos/
                ├── voice/
                ├── documents/
                └── stickers/
```

> **Hinweis:** Die HTML-Dateien verlinken Medien über relative Pfade nach `logseq-telegram/assets/`.
> Die Ordner `html/` und `logseq-telegram/` müssen daher immer gemeinsam unter demselben `BACKUP_DIR` bleiben.

---

## Konfiguration (`config.py`)

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `BACKUP_DIR` | `"backups"` | Zielordner für alle Ausgaben |
| `WHITELIST` | `[]` | Nur diese Chat-IDs sichern — leer bedeutet alle |
| `BLACKLIST` | `[]` | Diese Chat-IDs immer überspringen |
| `EXPORT_FORMATS` | `["html", "logseq"]` | Standardmäßig aktive Exportformate |
| `SKIP_MEDIA_TYPES` | `["video", "audio"]` | Für diese Typen wird nur ein Telegram-Link gespeichert, kein Download |
| `MAX_DOWNLOAD_SIZE_MB` | `1` | Maximale Dateigröße für Downloads in MB (`None` = kein Limit) |
| `LOGSEQ_DATE_FORMAT` | `"%Y_%m_%d"` | Dateinamen-Format für Journal-Einträge |
| `LOGSEQ_JOURNAL_DIR` | `None` | Pfad zum Logseq-Journals-Ordner (siehe Logseq-Integration) |
| `LOGSEQ_PAGES_DIR` | `None` | Pfad zum Logseq-Pages-Ordner |
| `LOGSEQ_ASSETS_DIR` | `None` | Pfad zum Logseq-Assets-Ordner |

### Medien-Einstellungen

Standardmäßig werden Fotos und Sprachnachrichten immer heruntergeladen, Videos und Musik nur verlinkt.

| Typ | Standard | Unterordner |
|-----|----------|-------------|
| Fotos | Download | `media/photos/` |
| Sprachnachrichten | Download | `media/voice/` |
| Dokumente / PDFs | Download wenn ≤ `MAX_DOWNLOAD_SIZE_MB` | `media/documents/` |
| Sticker | Download wenn ≤ `MAX_DOWNLOAD_SIZE_MB` | `media/stickers/` |
| Videos | nur Telegram-Link | — |
| Musik / Audio | nur Telegram-Link | — |

Alles herunterladen (inkl. Videos, ohne Größenlimit):
```python
SKIP_MEDIA_TYPES = []
MAX_DOWNLOAD_SIZE_MB = None
```

---

## Logseq-Integration

Jede Nachricht landet als Block im Tagesjournal:

```markdown
- [[Telegram]] [[Ralf @ralf_tg]] #telegram-backup
  - 14:30 [[Ralf @ralf_tg]]: Hallo!
  - 14:31 [[Ich @mein_username]]: Hi!
    - 🖼 ![](../../assets/1234567890_Ralf/media/photos/12345.jpg)
  - 14:32 [[Ralf @ralf_tg]]: Schau mal das Video
    - 🎥 [Telegram-Link](https://t.me/c/.../12346)
```

Für jeden Teilnehmer wird automatisch eine Page angelegt (`Rufname @username`). Bestehende Pages werden nie überschrieben.

### Modus A — direkt in einen bestehenden Graphen schreiben

In `config.py` die Pfade zum eigenen Logseq-Graphen eintragen:

```python
LOGSEQ_JOURNAL_DIR = "/home/user/logseq/journals"
LOGSEQ_PAGES_DIR   = "/home/user/logseq/pages"
LOGSEQ_ASSETS_DIR  = "/home/user/logseq/assets"
```

Ab sofort schreibt jeder Backup-Lauf direkt in diesen Graphen.

### Modus B — nachträglich übertragen mit `merge_to_logseq.py`

Ohne gesetzte Pfade landet alles in `backups/logseq-telegram/`. Dieser Ordner kann als eigener Logseq-Graph geöffnet oder mit folgendem Befehl in einen bestehenden Graphen übertragen werden:

```bash
# Vorschau — nichts wird geschrieben:
python merge_to_logseq.py --dry-run

# Übertragen:
python merge_to_logseq.py
```

Dazu müssen `LOGSEQ_JOURNAL_DIR` und `LOGSEQ_PAGES_DIR` in `config.py` gesetzt sein (LOGSEQ_ASSETS_DIR ist für merge nicht nötig).

**Sicherheitsgarantien beider Modi:**
- Journal-Einträge werden nur angehängt, nie überschrieben
- Pages werden nur neu angelegt, wenn sie noch nicht existieren
- Bereits übertragene Inhalte werden nicht doppelt eingefügt

---

## Automatischer Cron-Job

```bash
crontab -e
```

Täglich um 3 Uhr morgens sichern:

```
0 3 * * * cd /pfad/zum/projekt && .venv/bin/python backup.py
```

---

## Logseq-Export zurücksetzen

Falls der Logseq-Export neu generiert werden soll (z. B. nach manueller Löschung):

```bash
rm backups/json/{id}_{name}/.logseq_manifest.json
python backup.py --export logseq
```

Das Manifest verhindert Duplikate — ohne es werden alle gespeicherten Nachrichten neu exportiert.

---

## Fehlerbehebung

**`ModuleNotFoundError`** — venv ist nicht aktiviert:
```bash
source .venv/bin/activate
```

**`KeyError: 'TELEGRAM_API_ID'`** — `.env`-Datei fehlt oder ist unvollständig. Prüfen ob die Datei existiert und alle drei Werte eingetragen sind.

**`Backup läuft bereits.`** — Es läuft noch ein anderer Backup-Prozess, oder ein voriger Lauf wurde unsauber beendet. Lock-Datei manuell entfernen:
```bash
rm backups/.backup.lock
```

**Login-Code wird nicht angefragt beim zweiten Start** — Das ist normal. Die Session wird in `session/` gespeichert und wiederverwendet.
