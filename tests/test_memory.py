import importlib

import pytest


@pytest.fixture
def mem(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    import memory
    return importlib.reload(memory)


def test_remember_recall_forget(mem):
    assert mem.remember("Lieblingsgetränk", "Espresso") == "gespeichert"
    assert mem.remember("Lieblingsgetränk", "Cappuccino") == "aktualisiert"
    assert mem.recall("lieblingsgetränk") == "Cappuccino\n\n_Stand: " + mem.date.today().isoformat() + "_"
    assert "Lieblingsgetränk" in (mem.MEMORY_DIR / "MEMORY.md").read_text(encoding="utf-8")
    assert mem.forget("Lieblingsgetränk")
    assert mem.all_memories() == []


def test_slug_umlauts(mem):
    assert mem.slugify("Größe & Übung") == "groesse-uebung"


def test_search(mem):
    mem.remember("Plattform", "Sven programmiert auf Windows")
    mem.remember("Getränk", "Espresso")
    assert [m["title"] for m in mem.search("welches windows")] == ["Plattform"]


def test_mcp_tools(mem):
    import memory_mcp
    importlib.reload(memory_mcp)
    r = memory_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "remember", "arguments": {"title": "A", "content": "B"}}})
    assert r["result"]["isError"] is False
    r = memory_mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                           "params": {"name": "remember", "arguments": {"title": "", "content": "B"}}})
    assert r["result"]["isError"] is True
