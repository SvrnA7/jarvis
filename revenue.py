"""
revenue.py — Einnahmen der eigenen Apps aus RevenueCat lesen (nur lesend).

Braucht einen RevenueCat-API-Key der Version 2 (Secret Key) in
REVENUECAT_API_KEY. Lege ihn im RevenueCat-Dashboard unter
Projekt → API Keys an und gib ihm nur Leserechte:
  - Project configuration: Read  (für die Liste der Projekte/Apps)
  - Charts & metrics: Read       (für Umsatz, MRR, Abos)
Ein Key gilt für ein Projekt. Für mehrere Projekte: mehrere Keys,
kommagetrennt in REVENUECAT_API_KEY.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import httpx

API = "https://api.revenuecat.com/v2"
CACHE_SECONDS = 300  # Charts-API erlaubt nur 25 Anfragen pro Minute

# Kennzahlen, die Jarvis vorliest, in dieser Reihenfolge.
WANTED = ["revenue", "mrr", "active_subscriptions", "active_trials", "new_customers"]

_cache: dict[str, tuple[float, list[dict]]] = {}


class RevenueError(Exception):
    pass


def api_keys() -> list[str]:
    return [k.strip() for k in os.environ.get("REVENUECAT_API_KEY", "").split(",") if k.strip()]


def _get(client: httpx.Client, key: str, path: str, **params) -> dict:
    r = client.get(f"{API}{path}", params=params or None,
                   headers={"Authorization": f"Bearer {key}"}, timeout=15)
    if r.status_code in (401, 403):
        raise RevenueError("RevenueCat lehnt den API-Key ab. Prüfe, ob es ein v2-Secret-Key mit Leserechten ist.")
    if r.status_code == 429:
        raise RevenueError("RevenueCat-Ratenlimit erreicht, bitte gleich nochmal versuchen.")
    if r.status_code != 200:
        raise RevenueError(f"RevenueCat antwortet mit Status {r.status_code}.")
    return r.json()


def projects(client: httpx.Client) -> list[tuple[str, dict]]:
    """Alle Projekte, die die konfigurierten Keys sehen dürfen, als (key, projekt)."""
    out, seen = [], set()
    for key in api_keys():
        for p in _get(client, key, "/projects").get("items", []):
            if p["id"] not in seen:
                seen.add(p["id"])
                out.append((key, p))
    return out


def overview(client: httpx.Client, key: str, project_id: str, currency: str) -> list[dict]:
    hit = _cache.get(project_id + currency)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    data = _get(client, key, f"/projects/{project_id}/metrics/overview", currency=currency)
    metrics = data.get("metrics", [])
    _cache[project_id + currency] = (time.monotonic(), metrics)
    return metrics


def fmt_value(m: dict, currency: str) -> str:
    v = m.get("value")
    if not isinstance(v, (int, float)):
        return str(v)
    if m.get("unit") in ("$", "€", "£") or m.get("id") in ("revenue", "mrr"):
        s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s} {currency}"
    return f"{int(v):,}".replace(",", ".")


def report(app: Optional[str] = None, client: Optional[httpx.Client] = None) -> str:
    if not api_keys():
        return ("Kein RevenueCat-Key eingerichtet. Trage REVENUECAT_API_KEY in die .env ein "
                "(v2-Secret-Key mit Leserechten).")
    currency = os.environ.get("REVENUECAT_CURRENCY", "EUR").upper()
    own = client is None
    client = client or httpx.Client()
    try:
        found = projects(client)
        if app:
            needle = app.strip().lower()
            found = [(k, p) for k, p in found if needle in p.get("name", "").lower()]
            if not found:
                return f"Keine App namens '{app}' in RevenueCat gefunden."
        if not found:
            return "Der Key sieht keine Projekte in RevenueCat."
        blocks = []
        for key, p in found:
            metrics = {m["id"]: m for m in overview(client, key, p["id"], currency)}
            lines = [f"{p.get('name', p['id'])}:"]
            for mid in WANTED:
                if mid in metrics:
                    m = metrics[mid]
                    lines.append(f"- {m.get('name', mid)}: {fmt_value(m, currency)}"
                                 + (f" ({m['description']})" if m.get("description") else ""))
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
    except RevenueError as e:
        return str(e)
    except httpx.HTTPError:
        return "RevenueCat ist gerade nicht erreichbar."
    finally:
        if own:
            client.close()
