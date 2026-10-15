"""
memory.py — Jarvis' Langzeitgedächtnis als Ordner aus Markdown-Dateien.

Eine Datei pro Fakt, dazu ein Index (MEMORY.md), den das Gehirn bei jedem
Start sieht. Alles ist normaler Text: Du kannst es in jedem Editor lesen,
korrigieren oder löschen.
"""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
DATA = Path(os.environ.get("JARVIS_DATA_DIR") or ROOT / "data")
MEMORY_DIR = DATA / "memory"
INDEX = "MEMORY.md"
MAX_FACT_CHARS = 2000


def slugify(title: str) -> str:
    s = title.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "notiz"


def _path(title: str) -> Path:
    return MEMORY_DIR / f"{slugify(title)}.md"


def _parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    title, body = path.stem, text
    if text.startswith("# "):
        first, _, body = text.partition("\n")
        title = first[2:].strip()
    return {"title": title, "slug": path.stem, "content": body.strip()}


def all_memories() -> list[dict]:
    if not MEMORY_DIR.exists():
        return []
    return [_parse(p) for p in sorted(MEMORY_DIR.glob("*.md")) if p.name != INDEX]


def remember(title: str, content: str) -> str:
    title, content = title.strip(), content.strip()
    if not title or not content:
        raise ValueError("Titel und Inhalt dürfen nicht leer sein")
    if len(content) > MAX_FACT_CHARS:
        raise ValueError(f"Zu lang, höchstens {MAX_FACT_CHARS} Zeichen pro Erinnerung")
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(title)
    existed = path.exists()
    path.write_text(f"# {title}\n\n{content}\n\n_Stand: {date.today().isoformat()}_\n", encoding="utf-8")
    write_index()
    return "aktualisiert" if existed else "gespeichert"


def forget(title: str) -> bool:
    path = _path(title)
    if not path.exists():
        # auch über den angezeigten Titel finden
        match = [m for m in all_memories() if m["title"].lower() == title.strip().lower()]
        if not match:
            return False
        path = MEMORY_DIR / f"{match[0]['slug']}.md"
    path.unlink()
    write_index()
    return True


def recall(title: str) -> str | None:
    path = _path(title)
    if path.exists():
        return _parse(path)["content"]
    for m in all_memories():
        if m["title"].lower() == title.strip().lower():
            return m["content"]
    return None


def search(query: str) -> list[dict]:
    words = [w for w in query.lower().split() if len(w) > 2]
    hits = []
    for m in all_memories():
        hay = (m["title"] + " " + m["content"]).lower()
        score = sum(hay.count(w) for w in words)
        if score:
            hits.append((score, m))
    return [m for _, m in sorted(hits, key=lambda x: -x[0])[:5]]


def summary_line(m: dict) -> str:
    first = m["content"].splitlines()[0] if m["content"] else ""
    return f"- {m['title']}: {first[:140]}"


def write_index() -> str:
    lines = [summary_line(m) for m in all_memories()]
    text = "# Gedächtnis\n\n" + ("\n".join(lines) if lines else "(noch leer)") + "\n"
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    (MEMORY_DIR / INDEX).write_text(text, encoding="utf-8")
    return text
