#!/usr/bin/env python3
"""Überträgt Telegram-Backup-Daten in den Logseq-Hauptgraphen.

Regeln:
  - Journal-Einträge werden nur angehängt, nie überschrieben
  - Pages werden nur neu angelegt, nie überschrieben
  - Bereits übertragene Inhalte werden nicht doppelt eingefügt
"""

import json
import sys
from pathlib import Path

import config


MERGE_MANIFEST_FILE = Path(config.BACKUP_DIR) / "_merge_manifest.json"


def load_manifest():
    if MERGE_MANIFEST_FILE.exists():
        return json.loads(MERGE_MANIFEST_FILE.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest):
    MERGE_MANIFEST_FILE.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def merge_journals(backup_journals_dir, target_journals_dir, manifest, dry_run):
    """Hängt neue Journal-Inhalte an den Hauptgraph an."""
    merged = 0

    for backup_file in sorted(backup_journals_dir.glob("*.md")):
        key = str(backup_file.resolve())
        last_offset = manifest.get(key, 0)

        raw = backup_file.read_bytes()
        new_bytes = raw[last_offset:]

        if not new_bytes.strip():
            continue

        target_file = target_journals_dir / backup_file.name

        if dry_run:
            print(f"  [dry-run] Journal anhängen: {backup_file.name}")
            merged += 1
            continue

        # Sicherstellen, dass die Zieldatei mit einem Zeilenumbruch endet
        needs_newline = False
        if target_file.exists() and target_file.stat().st_size > 0:
            with open(target_file, "rb") as f:
                f.seek(-1, 2)
                needs_newline = f.read(1) != b"\n"

        with open(target_file, "ab") as f:
            if needs_newline:
                f.write(b"\n")
            f.write(new_bytes)

        manifest[key] = len(raw)
        print(f"  Journal: {backup_file.name}")
        merged += 1

    return merged


def merge_pages(backup_pages_dir, target_pages_dir, dry_run):
    """Kopiert neue Pages in den Hauptgraphen, überschreibt nie bestehende."""
    new_pages = 0

    for backup_page in sorted(backup_pages_dir.glob("*.md")):
        target_page = target_pages_dir / backup_page.name
        if target_page.exists():
            continue

        if dry_run:
            print(f"  [dry-run] Neue Page: {backup_page.name}")
        else:
            target_page.write_bytes(backup_page.read_bytes())
            print(f"  Page neu: {backup_page.name}")

        new_pages += 1

    return new_pages


def main(dry_run=False):
    target_journal_dir = config.LOGSEQ_JOURNAL_DIR
    target_pages_dir   = config.LOGSEQ_PAGES_DIR

    if not target_journal_dir or not target_pages_dir:
        print("Fehler: LOGSEQ_JOURNAL_DIR und LOGSEQ_PAGES_DIR müssen in config.py gesetzt sein.")
        print("")
        print("Beispiel:")
        print('  LOGSEQ_JOURNAL_DIR = "/home/daniel/logseq/journals"')
        print('  LOGSEQ_PAGES_DIR   = "/home/daniel/logseq/pages"')
        sys.exit(1)

    logseq_base    = Path(config.BACKUP_DIR) / "logseq-telegram"
    backup_journals = logseq_base / "journals"
    backup_pages    = logseq_base / "pages"

    if not backup_journals.exists():
        print("Keine Logseq-Backup-Daten gefunden.")
        print(f"Erwartet unter: {backup_journals}")
        sys.exit(0)

    target_journals = Path(target_journal_dir)
    target_pages    = Path(target_pages_dir)
    target_journals.mkdir(parents=True, exist_ok=True)
    target_pages.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()

    print(f"Quelle:  {logseq_base}")
    print(f"Ziel:    journals → {target_journals}")
    print(f"         pages    → {target_pages}")
    print()

    total_journals = merge_journals(backup_journals, target_journals, manifest, dry_run)
    total_pages = merge_pages(backup_pages, target_pages, dry_run) if backup_pages.exists() else 0

    if not dry_run:
        save_manifest(manifest)

    label = "[dry-run] " if dry_run else ""
    print(f"\n{label}Fertig: {total_journals} Journal-Datei(en), {total_pages} neue Page(s) übertragen.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Telegram-Backup → Logseq-Graph")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Zeigt was übertragen würde, ohne etwas zu schreiben",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
