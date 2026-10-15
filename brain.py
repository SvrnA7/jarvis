"""
brain.py — Jarvis' "Gehirn": EIN langlebiger `claude -p` Prozess.

Wie im Original läuft das Gehirn über das Claude-Code-Abo des Nutzers, nicht
über einen API-Key. Eingaben gehen als stream-json über stdin hinein, die
Antwort kommt als stream-json zurück und wird satzweise weitergereicht, damit
die Sprachausgabe schon beginnt, während der Rest noch geschrieben wird.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import AsyncIterator, Optional

log = logging.getLogger("jarvis.brain")

import memory

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "jarvis_home" / "CLAUDE.md"
# Arbeitsverzeichnis des Gehirns. Claude Code liest die CLAUDE.md dort selbst ein,
# so muss die Persona nicht als (unter Windows heikles) Kommandozeilenargument mit.
HOME = memory.DATA / "home"

# Die CLI bevorzugt still einen geerbten ANTHROPIC_API_KEY vor dem Login.
# Damit nie versehentlich über die API abgerechnet wird, fliegt alles raus.
SCRUBBED_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_")
SCRUBBED_KEYS = {"CLAUDECODE"}

# Satzende: . ! ? … gefolgt von Leerraum. Abkürzungen wie "z. B." sind selten
# genug in gesprochener Sprache, dass ein simpler Splitter reicht.
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def child_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items()
            if not k.startswith(SCRUBBED_PREFIXES) and k not in SCRUBBED_KEYS}


def persona() -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    name = os.environ.get("USER_NAME")
    if name:
        text += f"\n## Der Nutzer\nEr heißt {name}.\n"
    text += "\n## Was du über ihn weißt (dein Gedächtnis)\n\n" + memory.write_index()
    return text


def prepare_home() -> Path:
    """Schreibt CLAUDE.md (Persona + Gedächtnisindex) und die MCP-Konfiguration."""
    HOME.mkdir(parents=True, exist_ok=True)
    (HOME / "CLAUDE.md").write_text(persona(), encoding="utf-8")
    # Schlüssel wie REVENUECAT_API_KEY erbt der Werkzeug-Server aus der Umgebung,
    # damit sie nicht zusätzlich im Klartext in dieser Datei landen.
    env = {"JARVIS_DATA_DIR": str(memory.DATA), "PYTHONIOENCODING": "utf-8"}
    cfg = {"mcpServers": {"jarvis": {
        "command": sys.executable, "args": [str(ROOT / "jarvis_mcp.py")], "env": env,
    }}}
    path = HOME / "mcp.json"
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return path


def claude_executable() -> str:
    # Unter Windows installiert npm "claude.cmd"; which() findet beides.
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code nicht gefunden: npm install -g @anthropic-ai/claude-code")
    return exe


class Brain:
    def __init__(self, model: str = "sonnet"):
        self.model = model
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.lock = asyncio.Lock()  # eine Runde zur Zeit

    def command(self, mcp_config: Path) -> list[str]:
        return [
            claude_executable(), "-p",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--include-partial-messages", "--verbose",
            "--model", self.model,
            "--mcp-config", str(mcp_config), "--strict-mcp-config",
            "--allowedTools", "WebSearch,WebFetch,mcp__jarvis__remember,mcp__jarvis__recall,"
                              "mcp__jarvis__forget,mcp__jarvis__list_memories,mcp__jarvis__app_revenue",
        ]

    async def start(self) -> None:
        if self.proc and self.proc.returncode is None:
            return
        log.info("Starte Gehirn: claude -p (%s)", self.model)
        cmd = self.command(prepare_home())
        # stderr in eine Datei: eine ungelesene Pipe kann volllaufen und alles blockieren.
        self.stderr = open(HOME / "brain-stderr.log", "ab")
        self.proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(HOME), env=child_env(),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=self.stderr, limit=16 * 1024 * 1024,
        )

    async def stop(self) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            await self.proc.wait()
        if getattr(self, "stderr", None):
            self.stderr.close()

    async def ask(self, text: str) -> AsyncIterator[str]:
        """Schickt eine Nutzeräußerung und liefert die Antwort Satz für Satz."""
        async with self.lock:
            await self.start()
            assert self.proc and self.proc.stdin and self.proc.stdout
            msg = {"type": "user", "message": {"role": "user", "content": text}}
            self.proc.stdin.write((json.dumps(msg) + "\n").encode())
            await self.proc.stdin.drain()

            buf = ""
            async for event in self._events():
                kind = event.get("type")
                if kind == "stream_event":
                    ev = event.get("event", {})
                    delta = ev.get("delta", {})
                    if ev.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                        buf += delta.get("text", "")
                        *done, buf = SENTENCE_END.split(buf)
                        for s in done:
                            if s.strip():
                                yield s.strip()
                    elif ev.get("type") == "message_stop" and buf.strip():
                        # Text vor einem Werkzeugaufruf endet ohne Satzzeichen.
                        yield buf.strip()
                        buf = ""
                elif kind == "result":
                    if buf.strip():
                        yield buf.strip()
                    if event.get("is_error"):
                        log.error("Gehirn meldet Fehler: %s", event.get("result"))
                    return

    async def _events(self) -> AsyncIterator[dict]:
        assert self.proc and self.proc.stdout
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                log.error("Gehirn beendet, Details in %s", HOME / "brain-stderr.log")
                self.proc = None
                yield {"type": "result", "is_error": True, "result": "Prozess beendet"}
                return
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


class FakeBrain:
    """Für Tests ohne Claude: wiederholt, was gesagt wurde."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    async def ask(self, text: str) -> AsyncIterator[str]:
        await asyncio.sleep(0.2)
        yield f"Sie sagten: {text}."
        yield "Das Gehirn läuft im Testmodus, Sir."
