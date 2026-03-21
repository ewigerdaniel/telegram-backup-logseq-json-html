import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import config


MEDIA_EMOJI = {
    "photo":    "🖼",
    "voice":    "🎤",
    "document": "📄",
    "sticker":  "🎭",
    "video":    "🎥",
    "audio":    "🎵",
}


def sanitize_page_name(name):
    """Entfernt Zeichen, die in Logseq-Seitennamen nicht erlaubt sind."""
    return re.sub(r'[#\[\]|^{}]', '', name or "").strip()


def build_page_name(sender_name, sender_username):
    """Baut den Logseq-Seitennamen: 'Rufname @username' oder nur 'Rufname'."""
    name = sanitize_page_name(sender_name)
    if sender_username:
        return f"{name} @{sender_username}"
    return name


class LogseqExporter:
    def __init__(self, manifest_dir, journals_dir, pages_dir):
        self.manifest_file = Path(manifest_dir) / ".logseq_manifest.json"
        self.journals_dir  = Path(journals_dir)
        self.pages_dir     = Path(pages_dir)

    def _load_manifest(self):
        if self.manifest_file.exists():
            return set(json.loads(self.manifest_file.read_text()))
        return set()

    def _save_manifest(self, written_ids):
        self.manifest_file.write_text(
            json.dumps(sorted(written_ids), indent=2),
            encoding="utf-8",
        )

    def _ensure_participant_page(self, sender_name, sender_username):
        safe_name = build_page_name(sender_name, sender_username)
        if not safe_name:
            return
        page_file = self.pages_dir / f"{safe_name}.md"
        if not page_file.exists():
            page_file.write_text(
                f"tags:: telegram-contact\n\n- Telegram-Kontakt\n",
                encoding="utf-8",
            )

    def _resolve_media_path(self, local_path):
        """Gibt den Medienpfad relativ zum Journal-Verzeichnis zurück."""
        p = Path(local_path)
        if p.is_absolute():
            return os.path.relpath(p, self.journals_dir)
        return local_path

    def _media_line(self, media, indent):
        """Gibt die Medienzeile für einen Logseq-Block zurück."""
        if not media:
            return None
        emoji = MEDIA_EMOJI.get(media["type"], "📎")

        if media.get("local_path"):
            rel = self._resolve_media_path(media["local_path"])
            if media["type"] == "photo":
                return f"{indent}  - {emoji} ![]({rel})"
            else:
                return f"{indent}  - {emoji} [[{rel}]]"

        if media.get("telegram_link"):
            return f"{indent}  - {emoji} [Telegram-Link]({media['telegram_link']})"

        return None

    def _format_message(self, msg, indent="  "):
        date_obj = datetime.fromisoformat(msg["date"])
        time_str = date_obj.strftime("%H:%M")
        sender = build_page_name(msg["sender_name"], msg.get("sender_username"))

        text = (msg["text"] or "").replace("\n", f"\n{indent}  ")

        if msg.get("forwarded_from"):
            fwd = sanitize_page_name(msg["forwarded_from"])
            header = f"{indent}- {time_str} [[{sender}]] (↩ [[{fwd}]]): {text}"
        else:
            header = f"{indent}- {time_str} [[{sender}]]: {text}"

        lines = [header]

        media_line = self._media_line(msg.get("media"), indent)
        if media_line:
            lines.append(media_line)

        if msg.get("reply_to_id"):
            lines.append(f"{indent}  - ↩ Antwort auf Nachricht {msg['reply_to_id']}")

        return "\n".join(lines)

    def export(self, messages, chat_name, chat_username=None):
        if not messages:
            return

        self.journals_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)

        written_ids = self._load_manifest()
        new_messages = [m for m in messages if m["id"] not in written_ids]

        if not new_messages:
            print(f"  Logseq: keine neuen Nachrichten.")
            return

        # Nach Datum gruppieren
        by_date = defaultdict(list)
        for msg in new_messages:
            date_obj = datetime.fromisoformat(msg["date"])
            date_key = date_obj.strftime(config.LOGSEQ_DATE_FORMAT)
            by_date[date_key].append(msg)
            self._ensure_participant_page(msg["sender_name"], msg.get("sender_username"))

        safe_chat = build_page_name(chat_name, chat_username)

        for date_key, day_messages in sorted(by_date.items()):
            journal_file = self.journals_dir / f"{date_key}.md"

            block_lines = [f"- [[Telegram]] [[{safe_chat}]] #telegram-backup"]
            for msg in day_messages:
                block_lines.append(self._format_message(msg))
            block = "\n".join(block_lines) + "\n\n"

            with open(journal_file, "a", encoding="utf-8") as f:
                f.write(block)

        written_ids.update(m["id"] for m in new_messages)
        self._save_manifest(written_ids)

        print(f"  Logseq: {len(new_messages)} Nachrichten in {self.journals_dir}")
