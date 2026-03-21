import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

import config


URL_RE = re.compile(r'(https?://[^\s<>"\']+)')


def autolink(text):
    """Wandelt URLs im Text in klickbare Links um."""
    def replace(m):
        url = m.group(1)
        return f'<a href="{url}" target="_blank" rel="noopener">{url}</a>'
    return Markup(URL_RE.sub(replace, str(text)))


def file_uri(path):
    """Gibt absoluten Pfad als file://-URI zurück, relativen Pfad unverändert."""
    if not path:
        return path
    p = Path(path)
    if p.is_absolute():
        return p.as_uri()  # → file:///absoluter/pfad/foto.jpg
    return path


class HtmlExporter:
    def __init__(self, html_dir):
        self.html_dir = Path(html_dir)

    def export(self, messages, chat_name):
        templates_dir = Path(__file__).parent.parent / "templates"
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )
        env.filters["autolink"] = autolink
        env.filters["file_uri"] = file_uri
        template = env.get_template("chat.html")
        html = template.render(chat_name=chat_name, messages=messages)

        out_file = self.html_dir / "index.html"
        out_file.write_text(html, encoding="utf-8")
        print(f"  HTML: {out_file}")
