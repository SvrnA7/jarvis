"""
tts.py — Sprachausgabe, austauschbar über TTS_PROVIDER.

browser    : kein Server-Audio; der Browser spricht selbst (speechSynthesis).
             Kostenlos und ohne Key, klingt aber nach Systemstimme.
elevenlabs : ElevenLabs, sehr gute deutsche Stimmen.
fish       : Fish Audio, wie im Original.

Gibt MP3-Bytes zurück oder None (dann spricht der Browser als Fallback).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger("jarvis.tts")


async def synthesize(text: str, client: httpx.AsyncClient) -> Optional[bytes]:
    provider = os.environ.get("TTS_PROVIDER", "browser").lower()
    try:
        if provider == "elevenlabs":
            return await _elevenlabs(text, client)
        if provider == "fish":
            return await _fish(text, client)
    except httpx.HTTPError as e:
        log.error("TTS-Fehler (%s): %s", provider, e)
    return None


async def _elevenlabs(text: str, client: httpx.AsyncClient) -> Optional[bytes]:
    key = os.environ.get("ELEVENLABS_API_KEY")
    voice = os.environ.get("ELEVENLABS_VOICE_ID")
    if not key or not voice:
        log.warning("ELEVENLABS_API_KEY oder ELEVENLABS_VOICE_ID fehlt")
        return None
    r = await client.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
        headers={"xi-api-key": key, "accept": "audio/mpeg"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=20,
    )
    if r.status_code != 200:
        log.error("ElevenLabs %s: %s", r.status_code, r.text[:200])
        return None
    return r.content


async def _fish(text: str, client: httpx.AsyncClient) -> Optional[bytes]:
    key = os.environ.get("FISH_API_KEY")
    if not key:
        log.warning("FISH_API_KEY fehlt")
        return None
    body = {"text": text, "format": "mp3", "mp3_bitrate": 128, "latency": "balanced"}
    if os.environ.get("FISH_VOICE_ID"):
        body["reference_id"] = os.environ["FISH_VOICE_ID"]
    r = await client.post(
        "https://api.fish.audio/v1/tts",
        headers={"Authorization": f"Bearer {key}"},
        json=body, timeout=20,
    )
    if r.status_code != 200:
        log.error("Fish %s: %s", r.status_code, r.text[:200])
        return None
    return r.content
