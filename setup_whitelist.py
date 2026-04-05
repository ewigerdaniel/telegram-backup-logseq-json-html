#!/usr/bin/env python3
"""Trägt alle verfügbaren Telegram-Chats kommentiert in die WHITELIST ein.

Verwendung:
    python setup_whitelist.py

Danach in config.py das # vor den gewünschten Chat-IDs entfernen.
"""

import asyncio
import re
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

import config


def get_chat_name(entity):
    if isinstance(entity, User):
        name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
        return name or entity.username or str(entity.id)
    if isinstance(entity, (Chat, Channel)):
        return entity.title or str(entity.id)
    return str(entity.id)


async def fetch_chats():
    Path(config.SESSION_NAME).parent.mkdir(exist_ok=True)
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.start(phone=config.PHONE)

    chats = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        chats.append((entity.id, get_chat_name(entity)))

    await client.disconnect()
    return chats


def update_config(chats):
    config_path = Path("config.py")
    text = config_path.read_text(encoding="utf-8")

    lines = [f"    # {cid},  # {name}" for cid, name in chats]
    new_block = "WHITELIST: list[int] = [\n" + "\n".join(lines) + "\n]"

    updated = re.sub(
        r"WHITELIST: list\[int\] = \[.*?\]",
        new_block,
        text,
        flags=re.DOTALL,
    )

    if updated == text:
        print("Fehler: WHITELIST-Block in config.py nicht gefunden.")
        return

    config_path.write_text(updated, encoding="utf-8")
    print(f"{len(chats)} Chats in config.py eingetragen.")
    print("Öffne config.py und entferne das  #  vor den Chats, die du sichern möchtest.")


async def main():
    print("Verbinde mit Telegram...")
    chats = await fetch_chats()
    print(f"{len(chats)} Chats gefunden.\n")
    for cid, name in chats:
        print(f"  {cid}  ·  {name}")
    print()
    update_config(chats)


if __name__ == "__main__":
    asyncio.run(main())
