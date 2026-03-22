#!/usr/bin/env python3
"""Telegram-Backup: Sichert Chats, Kanäle und Gruppen."""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import (
    Channel,
    Chat,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    Message as TelegramMessage,
    MessageMediaDocument,
    MessageMediaPhoto,
    User,
)

import config
from exporters.html_exporter import HtmlExporter
from exporters.json_exporter import JsonExporter
from exporters.logseq_exporter import LogseqExporter, build_page_name, sanitize_page_name


MENTION_RE = re.compile(r'\[([^\]]+)\]\(tg://user\?id=(\d+)\)')


async def resolve_mentions(client, text):
    """Ersetzt [Name](tg://user?id=XXX) durch [[Name @username]] für Logseq."""
    if not text or 'tg://user' not in text:
        return text

    parts = []
    offset = 0
    for match in MENTION_RE.finditer(text):
        parts.append(text[offset:match.start()])
        display_name = match.group(1)
        user_id = int(match.group(2))
        try:
            user = await client.get_entity(user_id)
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or display_name
            page_name = build_page_name(name, user.username)
        except Exception:
            page_name = sanitize_page_name(display_name)
        parts.append(f"[[{page_name}]]")
        offset = match.end()
    parts.append(text[offset:])
    return ''.join(parts)


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def get_chat_name(entity):
    if isinstance(entity, User):
        name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
        return name or entity.username or str(entity.id)
    if isinstance(entity, (Chat, Channel)):
        return entity.title or str(entity.id)
    return str(entity.id)


def _safe_name(chat_name):
    return re.sub(r'[<>:"/\\|?*]', '_', chat_name)


def get_json_dir(entity_id, chat_name):
    """JSON-Daten und State pro Chat."""
    return Path(config.BACKUP_DIR) / "json" / f"{entity_id}_{_safe_name(chat_name)}"


def get_html_dir(entity_id, chat_name):
    """HTML-Ausgabe pro Chat."""
    return Path(config.BACKUP_DIR) / "html" / f"{entity_id}_{_safe_name(chat_name)}"


def get_logseq_dirs():
    """Gibt (journals_dir, pages_dir, assets_base) zurück."""
    base = Path(config.BACKUP_DIR) / "logseq-telegram"
    journals = Path(config.LOGSEQ_JOURNAL_DIR) if config.LOGSEQ_JOURNAL_DIR else base / "journals"
    pages    = Path(config.LOGSEQ_PAGES_DIR)   if config.LOGSEQ_PAGES_DIR   else base / "pages"
    assets   = Path(config.LOGSEQ_ASSETS_DIR)  if config.LOGSEQ_ASSETS_DIR  else base / "assets"
    return journals, pages, assets


def make_telegram_link(entity, message_id):
    """Link zur Nachricht im aktuellen Chat. Gibt None zurück für private Chats."""
    if isinstance(entity, User):
        return None  # Private 1:1-Chats haben keine öffentliche URL
    if getattr(entity, 'username', None):
        return f"https://t.me/{entity.username}/{message_id}"
    # Private Gruppen/Kanäle ohne Username
    raw_id = str(abs(entity.id))
    if raw_id.startswith("100") and len(raw_id) > 10:
        raw_id = raw_id[3:]
    return f"https://t.me/c/{raw_id}/{message_id}"


def make_fwd_link(fwd_from):
    """Link zum Original einer weitergeleiteten Nachricht (falls aus einem Kanal)."""
    if not fwd_from:
        return None
    post_id = getattr(fwd_from, 'channel_post', None)
    if not post_id:
        return None
    from_id = getattr(fwd_from, 'from_id', None)
    if from_id and hasattr(from_id, 'channel_id'):
        return f"https://t.me/c/{from_id.channel_id}/{post_id}"
    return None


def classify_media(message):
    """Gibt den Medientyp zurück oder None."""
    media = message.media
    if media is None:
        return None

    if isinstance(media, MessageMediaPhoto):
        return "photo"

    if isinstance(media, MessageMediaDocument):
        doc = media.document
        if doc is None:
            return None
        attrs = doc.attributes

        for attr in attrs:
            if isinstance(attr, DocumentAttributeAudio):
                return "voice" if attr.voice else "audio"

        for attr in attrs:
            if isinstance(attr, DocumentAttributeVideo):
                return "video"

        mime = doc.mime_type or ""
        if mime in ("image/webp", "video/webm"):
            return "sticker"

        return "document"

    return None


def should_download(media_type):
    return media_type not in config.SKIP_MEDIA_TYPES


def is_within_size_limit(message):
    """Prüft ob die Datei das konfigurierte Größenlimit einhält."""
    if config.MAX_DOWNLOAD_SIZE_MB is None:
        return True
    if not isinstance(message.media, MessageMediaDocument):
        return True  # Fotos haben kein Limit
    doc = message.media.document
    if doc is None or not hasattr(doc, 'size'):
        return True
    return doc.size <= config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024


# ── Media-Download ───────────────────────────────────────────────────────────

async def download_media(client, message, media_type, assets_chat_dir):
    """Lädt Medien nach assets_chat_dir herunter. Gibt immer absoluten Pfad zurück."""
    subdir_map = {
        "photo":    "photos",
        "voice":    "voice",
        "document": "documents",
        "sticker":  "stickers",
        "audio":    "audio",
    }
    subdir = subdir_map.get(media_type, "other")
    media_dir = assets_chat_dir / "media" / subdir
    media_dir.mkdir(parents=True, exist_ok=True)

    if media_type == "photo":
        filename = f"{message.id}.jpg"
    elif media_type == "voice":
        filename = f"{message.id}.ogg"
    elif media_type in ("document", "audio", "sticker"):
        doc = message.media.document
        filename = None
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                filename = f"{message.id}_{attr.file_name}"
                break
        if not filename:
            ext = (doc.mime_type or "application/octet-stream").split("/")[-1]
            filename = f"{message.id}.{ext}"
    else:
        filename = f"{message.id}.bin"

    dest = media_dir / filename
    if not dest.exists():
        try:
            await client.download_media(message, file=dest)
        except Exception as e:
            print(f"  Warnung: Medien für Nachricht {message.id} konnten nicht heruntergeladen werden: {e}")
            return None

    return str(dest.resolve())


# ── Nachrichtenverarbeitung ──────────────────────────────────────────────────

async def process_message(client, message, entity, assets_chat_dir):
    """Konvertiert eine Telethon-Nachricht in unser Dict-Format."""
    # Absender
    try:
        sender = await message.get_sender()
    except Exception:
        sender = None

    if isinstance(sender, User):
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        sender_name = sender_name or sender.username or str(sender.id)
        sender_username = sender.username
    elif sender is not None:
        sender_name = getattr(sender, 'title', None) or str(sender.id)
        sender_username = getattr(sender, 'username', None)
    else:
        sender_name = "Unbekannt"
        sender_username = None

    # Medien
    media_info = None
    media_type = classify_media(message)
    if media_type:
        if should_download(media_type) and is_within_size_limit(message):
            local_path = await download_media(client, message, media_type, assets_chat_dir)
            # Fallback: wenn Download fehlschlägt, Telegram-Link speichern
            if local_path is None:
                link = make_fwd_link(message.fwd_from) or make_telegram_link(entity, message.id)
            else:
                link = None
            media_info = {
                "type": media_type,
                "local_path": local_path,
                "telegram_link": link,
            }
        else:
            link = make_fwd_link(message.fwd_from) or make_telegram_link(entity, message.id)
            media_info = {
                "type": media_type,
                "local_path": None,
                "telegram_link": link,
            }

    # Weitergeleitet von
    forwarded_from = None
    if message.fwd_from:
        fwd = message.fwd_from
        forwarded_from = getattr(fwd, 'from_name', None)
        if not forwarded_from and getattr(fwd, 'from_id', None):
            try:
                from_entity = await client.get_entity(fwd.from_id)
                if isinstance(from_entity, User):
                    name = f"{from_entity.first_name or ''} {from_entity.last_name or ''}".strip()
                    forwarded_from = name or from_entity.username or str(from_entity.id)
                else:
                    forwarded_from = getattr(from_entity, 'title', None) or str(from_entity.id)
            except Exception:
                pass

    text = await resolve_mentions(client, message.text or "")

    return {
        "id": message.id,
        "date": message.date.isoformat(),
        "sender_name": sender_name,
        "sender_username": sender_username,
        "text": text,
        "media": media_info,
        "reply_to_id": message.reply_to_msg_id if message.reply_to else None,
        "forwarded_from": forwarded_from,
    }


# ── State (inkrementelles Backup) ────────────────────────────────────────────

def load_state(json_dir):
    state_file = json_dir / "state.json"
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {"last_message_id": 0}


def save_state(json_dir, state):
    state_file = json_dir / "state.json"
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── Chat-Filter ──────────────────────────────────────────────────────────────

def is_chat_allowed(entity_id):
    if entity_id in config.BLACKLIST:
        return False
    if config.WHITELIST:
        return entity_id in config.WHITELIST
    return True


# ── Backup-Logik ─────────────────────────────────────────────────────────────

async def backup_chat(client, dialog, export_formats):
    entity = dialog.entity
    chat_name = get_chat_name(entity)
    json_dir  = get_json_dir(entity.id, chat_name)
    html_dir  = get_html_dir(entity.id, chat_name)
    json_dir.mkdir(parents=True, exist_ok=True)

    journals_dir, pages_dir, assets_base = get_logseq_dirs()
    assets_chat_dir = assets_base / json_dir.name

    state = load_state(json_dir)
    last_id = state.get("last_message_id", 0)

    print(f"\n→ {chat_name}  (ab Nachrichten-ID {last_id})")

    iter_kwargs = {}
    if last_id > 0:
        iter_kwargs["min_id"] = last_id

    raw = []
    async for message in client.iter_messages(entity, **iter_kwargs):
        if not isinstance(message, TelegramMessage):
            continue
        if message.text is None and message.media is None:
            continue
        raw.append(message)

    raw.sort(key=lambda m: m.id)

    new_messages = []
    for message in raw:
        msg_dict = await process_message(client, message, entity, assets_chat_dir)
        new_messages.append(msg_dict)

        if message.id > last_id:
            last_id = message.id

        preview = (msg_dict["text"] or f"[{msg_dict.get('media', {}) and msg_dict['media']['type']}]")[:60]
        print(f"  [{message.id}] {msg_dict['sender_name']}: {preview}")

    # Bestehende Nachrichten laden und zusammenführen
    json_file = json_dir / "messages.json"
    if json_file.exists():
        existing = json.loads(json_file.read_text(encoding="utf-8"))
    else:
        existing = []

    all_messages = existing + new_messages

    if not new_messages:
        print(f"  Keine neuen Nachrichten.")
    else:
        print(f"  {len(new_messages)} neue Nachrichten.")
        JsonExporter(json_dir).export(all_messages, chat_name)
        if "html" in export_formats:
            html_dir.mkdir(parents=True, exist_ok=True)
            HtmlExporter(html_dir).export(all_messages, chat_name)
        state["last_message_id"] = last_id
        state["chat_name"] = chat_name
        save_state(json_dir, state)

    # Logseq immer aus allen Nachrichten — Manifest verhindert Duplikate
    if "logseq" in export_formats:
        chat_username = getattr(entity, 'username', None) if isinstance(entity, User) else None
        LogseqExporter(json_dir, journals_dir, pages_dir).export(
            all_messages, chat_name, chat_username=chat_username
        )


# ── Einstiegspunkt ────────────────────────────────────────────────────────────

async def main(export_formats, list_chats=False):
    Path(config.SESSION_NAME).parent.mkdir(exist_ok=True)
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.start(phone=config.PHONE)

    if list_chats:
        print("\nVerfügbare Chats (ID · Name):")
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            name = get_chat_name(entity)
            eid = entity.id
            marker = ""
            if config.WHITELIST and eid in config.WHITELIST:
                marker = "  ✓ Whitelist"
            if eid in config.BLACKLIST:
                marker = "  ✗ Blacklist"
            print(f"  {eid}  ·  {name}{marker}")
        await client.disconnect()
        return

    backed_up = 0
    async for dialog in client.iter_dialogs():
        if is_chat_allowed(dialog.entity.id):
            await backup_chat(client, dialog, export_formats)
            backed_up += 1

    await client.disconnect()
    print(f"\nBackup abgeschlossen. {backed_up} Chat(s) verarbeitet.")


LOCK_FILE = Path(config.BACKUP_DIR) / ".backup.lock"


def acquire_lock():
    """Gibt True zurück wenn der Lock erfolgreich gesetzt wurde, sonst False."""
    if LOCK_FILE.exists():
        pid = LOCK_FILE.read_text().strip()
        # Prüfen ob der Prozess noch läuft
        try:
            os.kill(int(pid), 0)
            return False  # Prozess läuft noch
        except (ProcessLookupError, ValueError):
            pass  # Prozess existiert nicht mehr — veralteter Lock
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def release_lock():
    LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram-Backup")
    parser.add_argument(
        "--export",
        nargs="+",
        choices=["html", "logseq"],
        default=config.EXPORT_FORMATS,
        metavar="FORMAT",
        help="Exportformate: html, logseq (Standard: aus config.py)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Alle verfügbaren Chats auflisten und beenden",
    )
    args = parser.parse_args()

    if not args.list:
        if not acquire_lock():
            print("Backup läuft bereits. Abbruch.")
            sys.exit(0)

    try:
        asyncio.run(main(args.export, args.list))
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
    finally:
        if not args.list:
            release_lock()
