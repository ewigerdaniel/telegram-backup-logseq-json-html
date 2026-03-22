import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API credentials (from https://my.telegram.org)
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]

# Telethon session file location
SESSION_NAME = "session/telegram_backup"

# ── Chat-Auswahl ────────────────────────────────────────────────────────────
# IDs ermitteln mit: python backup.py --list
#
# WHITELIST: Nur diese Chats sichern. Leer = alle (minus Blacklist).
WHITELIST: list[int] = [
    # 1234567890,  # Max Mustermann
    # 9876543210,  # Familiengruppe
    # 1122334455,  # Arbeit
]

# BLACKLIST: Diese Chats immer überspringen.
BLACKLIST: list[int] = [
    # 5566778899,  # Newsletter-Bot
    # 1029384756,  # Spam
    # 1357924680,  # Archiviert
]

# ── Media ───────────────────────────────────────────────────────────────────
# Für diese Typen wird kein Download durchgeführt;
# stattdessen wird der Telegram-Link gespeichert.
SKIP_MEDIA_TYPES = ["video", "audio"]

# Maximale Dateigröße für den Download in MB (gilt für Dokumente, Audio, Sticker).
# Dateien die größer sind, werden verlinkt statt heruntergeladen.
# None = kein Limit (alles herunterladen, auch große Dateien und Videos)
MAX_DOWNLOAD_SIZE_MB = 1

# ── Output ──────────────────────────────────────────────────────────────────
BACKUP_DIR = "backups"

# Standardmäßig aktive Exportformate: "html" und/oder "logseq"
# Kann per CLI überschrieben werden: python backup.py --export html
EXPORT_FORMATS = ["html", "logseq"]

# ── Logseq ──────────────────────────────────────────────────────────────────
# Dateinamen-Format für Journal-Einträge (Standard Logseq: %Y_%m_%d)
LOGSEQ_DATE_FORMAT = "%Y_%m_%d"

# Optional: direkt in einen externen Logseq-Graphen schreiben.
# None = Ausgabe nach backups/logseq-telegram/ (Standard)
LOGSEQ_JOURNAL_DIR = None   # z.B. "/home/user/logseq/journals"
LOGSEQ_PAGES_DIR   = None   # z.B. "/home/user/logseq/pages"
LOGSEQ_ASSETS_DIR  = None   # z.B. "/home/user/logseq/assets"
