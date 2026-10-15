"""
server.py — FastAPI-Server: liefert die Oberfläche aus und verbindet
Mikrofon (Browser) → Gehirn (claude -p) → Stimme (TTS) über einen WebSocket.

Start:  python server.py   →  http://localhost:8340 in Chrome öffnen
"""
from __future__ import annotations

import argparse
import base64
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from brain import Brain, FakeBrain
import memory
import tts

ROOT = Path(__file__).parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("jarvis")


def load_env() -> None:
    """Minimaler .env-Leser, damit keine weitere Abhängigkeit nötig ist."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


load_env()
brain = FakeBrain() if os.environ.get("JARVIS_FAKE_BRAIN") == "1" \
    else Brain(model=os.environ.get("JARVIS_BRAIN_MODEL", "sonnet"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient()
    yield
    await brain.stop()
    await app.state.http.aclose()


app = FastAPI(lifespan=lifespan)

# Erlaubte Origins: nur die eigene Seite. Eine fremde Webseite, die du gerade
# besuchst, soll nicht per WebSocket in deinem Namen mit Jarvis sprechen.
def origin_ok(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin", "")
    host = ws.headers.get("host", "")
    return origin in (f"http://{host}", f"https://{host}")


@app.get("/api/config")
async def config():
    return {"tts": os.environ.get("TTS_PROVIDER", "browser"),
            "fake_brain": isinstance(brain, FakeBrain)}


@app.get("/api/memory")
async def memories():
    return memory.all_memories()


@app.websocket("/ws")
async def voice(ws: WebSocket):
    if not origin_ok(ws):
        await ws.close(code=4403)
        return
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") != "transcript" or not msg.get("text", "").strip():
                continue
            text = msg["text"].strip()
            log.info("Nutzer: %s", text)
            await ws.send_json({"type": "thinking"})
            async for sentence in brain.ask(text):
                log.info("Jarvis: %s", sentence)
                audio = await tts.synthesize(sentence, app.state.http)
                await ws.send_json({
                    "type": "sentence", "text": sentence,
                    "audio": base64.b64encode(audio).decode() if audio else None,
                })
            await ws.send_json({"type": "done"})
    except WebSocketDisconnect:
        pass


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8340)
    a = p.parse_args()
    uvicorn.run(app, host=a.host, port=a.port)
