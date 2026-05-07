"""Tests for the Bridge module."""
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("BRIDGE_TOKEN", "test-token")


def _client(enabled: bool):
    os.environ["BRIDGE_ENABLED"] = "true" if enabled else "false"
    # Clear cache
    from app.core import bridge_config
    bridge_config.get_bridge_settings.cache_clear()
    from app.main import app
    return TestClient(app)


def test_bridge_disabled_returns_503():
    c = _client(False)
    r = c.post("/api/v1/bridge/signal", json={
        "master_id": "low", "action": "OPEN", "symbol": "XAUUSD", "volume": 1.0
    }, headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 503


def test_bridge_invalid_token():
    c = _client(True)
    r = c.post("/api/v1/bridge/signal", json={
        "master_id": "low", "action": "OPEN", "symbol": "XAUUSD", "volume": 1.0
    }, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403


def test_bridge_invalid_payload_volume():
    c = _client(True)
    r = c.post("/api/v1/bridge/signal", json={
        "master_id": "low", "action": "OPEN", "symbol": "XAUUSD", "volume": 0
    }, headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 422


def test_bridge_invalid_action():
    c = _client(True)
    r = c.post("/api/v1/bridge/signal", json={
        "master_id": "low", "action": "FOO", "symbol": "XAUUSD", "volume": 1.0
    }, headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 422


def test_lot_calculator_proportional():
    from app.workers.bridge_distributor import calc_proportional, normalize_lot
    raw = calc_proportional(master_volume=1.0, master_balance=10000, client_balance=2500, risk=1.0)
    assert abs(raw - 0.25) < 1e-9
    assert normalize_lot(raw, min_lot=0.01, max_lot=100, step=0.01) == 0.25


def test_lot_too_small():
    from app.workers.bridge_distributor import calc_proportional, normalize_lot
    raw = calc_proportional(master_volume=0.01, master_balance=100000, client_balance=100, risk=1.0)
    assert normalize_lot(raw, min_lot=0.01, max_lot=100, step=0.01) == 0.0
