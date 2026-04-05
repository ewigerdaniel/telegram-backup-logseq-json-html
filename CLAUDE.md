# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate venv (required before running anything)
source .venv/bin/activate

# First-time setup: fetch all chats and write them commented into WHITELIST in config.py
python setup_whitelist.py

# List all available Telegram chats with IDs (manual alternative to setup_whitelist.py)
python backup.py --list

# Run full backup (formats from config.py)
python backup.py

# Run backup with specific export formats
python backup.py --export html
python backup.py --export logseq
python backup.py --export html logseq

# Transfer logseq-telegram/ data into an external Logseq graph
python merge_to_logseq.py
python merge_to_logseq.py --dry-run
```

## Architecture

All configuration lives in `config.py` (not environment variables, except Telegram credentials which go in `.env`).

**Data flow:**
1. `backup.py` connects via Telethon, fetches messages, downloads media, writes to `backups/json/{id}_{name}/messages.json`
2. `HtmlExporter` reads the message list and renders `backups/html/{id}_{name}/index.html` via Jinja2
3. `LogseqExporter` appends to `backups/logseq-telegram/journals/YYYY_MM_DD.md` and creates participant pages in `backups/logseq-telegram/pages/`
4. Media is always written to `backups/logseq-telegram/assets/{id}_{name}/media/` — HTML uses relative paths to reach it

**Incremental backup state:**
- `backups/json/{id}_{name}/state.json` — stores `last_message_id` per chat
- `backups/json/{id}_{name}/.logseq_manifest.json` — stores IDs already written to Logseq journals (prevents duplicates on re-runs)
- `backups/.backup.lock` — PID lock file, prevents parallel runs

**Message dict format** (passed between all exporters):
```python
{
    "id": int,
    "date": str,          # ISO format
    "sender_name": str,
    "sender_username": str | None,
    "text": str,          # may contain [[Name @username]] Logseq links from resolved mentions
    "media": {
        "type": str,      # photo/voice/document/sticker/video/audio
        "local_path": str | None,   # absolute path
        "telegram_link": str | None
    } | None,
    "reply_to_id": int | None,
    "forwarded_from": str | None
}
```

**Key design decisions:**
- `build_page_name(name, username)` in `logseq_exporter.py` is the single source of truth for Logseq page names — always `"Rufname @username"`. Both `backup.py` (for mention resolution) and `logseq_exporter.py` import and use this function.
- Inline Telegram mentions (`[Name](tg://user?id=XXX)`) are resolved in `process_message()` via `resolve_mentions()` and stored as `[[Name @username]]` in the text field. The HTML exporter strips `[[...]]` back to plain text.
- `SKIP_MEDIA_TYPES` controls which types are never downloaded. `MAX_DOWNLOAD_SIZE_MB` applies a size limit to `MessageMediaDocument` types only (photos are exempt). Both result in a Telegram link being stored instead.
- HTML uses relative paths from `html/{id}_{name}/` to `logseq-telegram/assets/` — these two directories must stay under the same `BACKUP_DIR`.

**Git remotes:**
- `origin` → Forgejo (self-hosted)
- `github` → GitHub

Push to both: `git push origin master && git push github master`
