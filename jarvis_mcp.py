"""
jarvis_mcp.py — kleiner MCP-Server (stdio, JSON-RPC), der dem Gehirn Jarvis'
eigene Werkzeuge gibt: Gedächtnis und Einnahmen. Wird von brain.py über
--mcp-config gestartet.
"""
from __future__ import annotations

import json
import sys

import memory
import revenue

TOOLS = [
    {
        "name": "remember",
        "description": "Etwas Dauerhaftes über den Nutzer oder seine Projekte merken, "
                       "z. B. Vorlieben, Namen, Entscheidungen. Ein Fakt pro Titel; "
                       "gleicher Titel überschreibt.",
        "inputSchema": {"type": "object", "properties": {
            "title": {"type": "string", "description": "kurzer Titel, z. B. 'Lieblingsessen'"},
            "content": {"type": "string", "description": "der Fakt in ein bis drei Sätzen"},
        }, "required": ["title", "content"]},
    },
    {
        "name": "recall",
        "description": "Eine Erinnerung vollständig lesen, per Titel oder Suchbegriff.",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "forget",
        "description": "Eine Erinnerung löschen, nur wenn der Nutzer das ausdrücklich will.",
        "inputSchema": {"type": "object", "properties": {
            "title": {"type": "string"}}, "required": ["title"]},
    },
    {
        "name": "list_memories",
        "description": "Alle gespeicherten Erinnerungen mit Titel und erster Zeile auflisten.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "app_revenue",
        "description": "Einnahmen der eigenen Apps aus RevenueCat lesen (nur lesend): Umsatz der "
                       "letzten 28 Tage, MRR, aktive Abos, Testphasen, neue Kunden. Ohne 'app' "
                       "kommen alle Apps.",
        "inputSchema": {"type": "object", "properties": {
            "app": {"type": "string", "description": "optional: Name oder Teil des App-Namens"}}},
    },
]


def call(name: str, args: dict) -> str:
    if name == "remember":
        return f"Erinnerung '{args['title']}' {memory.remember(args['title'], args['content'])}."
    if name == "recall":
        exact = memory.recall(args["query"])
        if exact:
            return exact
        hits = memory.search(args["query"])
        if not hits:
            return "Nichts dazu gespeichert."
        return "\n\n".join(f"{m['title']}:\n{m['content']}" for m in hits)
    if name == "forget":
        return "Gelöscht." if memory.forget(args["title"]) else "Keine solche Erinnerung."
    if name == "list_memories":
        return memory.write_index()
    if name == "app_revenue":
        return revenue.report(args.get("app"))
    raise ValueError(f"Unbekanntes Werkzeug: {name}")


def handle(req: dict) -> dict | None:
    method, rid = req.get("method"), req.get("id")
    if rid is None:  # Benachrichtigung, keine Antwort
        return None
    if method == "initialize":
        result = {"protocolVersion": req.get("params", {}).get("protocolVersion", "2024-11-05"),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "jarvis", "version": "0.1.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        p = req.get("params", {})
        try:
            text, err = call(p.get("name"), p.get("arguments") or {}), False
        except Exception as e:  # Fehler als Werkzeugergebnis melden, nicht abstürzen
            text, err = f"Fehler: {e}", True
        result = {"content": [{"type": "text", "text": text}], "isError": err}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Methode unbekannt"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def main() -> None:
    # Unter Windows sonst cp1252 statt UTF-8
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = handle(json.loads(line))
        except json.JSONDecodeError:
            continue
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
