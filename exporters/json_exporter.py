import json
from pathlib import Path


class JsonExporter:
    def __init__(self, chat_dir):
        self.chat_dir = Path(chat_dir)

    def export(self, messages, chat_name):
        out_file = self.chat_dir / "messages.json"
        out_file.write_text(
            json.dumps(messages, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  JSON: {out_file} ({len(messages)} Nachrichten gesamt)")
