from html import escape
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def render_email(name: str, **context: object) -> tuple[str, str]:
    values = {key: "" if value is None else str(value) for key, value in context.items()}
    text = _fill(_read(f"{name}.txt"), values)
    html = _fill(_read(f"{name}.html"), {key: escape(value) for key, value in values.items()})
    return text, html


def _read(filename: str) -> str:
    path = TEMPLATES_DIR / filename
    return path.read_text(encoding="utf-8")


def _fill(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered
