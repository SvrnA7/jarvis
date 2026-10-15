import httpx
import pytest

import revenue


def fake_client(status=200):
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer sk_test"
        if status != 200:
            return httpx.Response(status)
        if req.url.path == "/v2/projects":
            return httpx.Response(200, json={"object": "list", "items": [
                {"id": "proj1", "name": "Fitness App"}, {"id": "proj2", "name": "Notizen"}]})
        assert req.url.params["currency"] == "EUR"
        pid = req.url.path.split("/")[3]
        return httpx.Response(200, json={"object": "overview_metrics", "currency": "EUR", "metrics": [
            {"id": "revenue", "name": "Revenue", "unit": "€", "value": 1234.5 if pid == "proj1" else 10},
            {"id": "active_subscriptions", "name": "Active Subscriptions", "unit": "#", "value": 1200},
            {"id": "other", "name": "Ignoriert", "value": 1},
        ]})
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("REVENUECAT_API_KEY", "sk_test")
    monkeypatch.delenv("REVENUECAT_CURRENCY", raising=False)
    revenue._cache.clear()


def test_all_apps():
    out = revenue.report(client=fake_client())
    assert "Fitness App:" in out and "Notizen:" in out
    assert "Revenue: 1.234,50 EUR" in out
    assert "Active Subscriptions: 1.200" in out
    assert "Ignoriert" not in out


def test_filter_by_name():
    out = revenue.report("fitness", client=fake_client())
    assert "Fitness App" in out and "Notizen" not in out
    assert "Keine App" in revenue.report("gibtsnicht", client=fake_client())


def test_bad_key():
    assert "lehnt den API-Key ab" in revenue.report(client=fake_client(401))


def test_no_key(monkeypatch):
    monkeypatch.delenv("REVENUECAT_API_KEY")
    assert "Kein RevenueCat-Key" in revenue.report()
