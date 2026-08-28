import hashlib
import hmac


def test_webhook_open_when_secret_unset(client):
    res = client.post("/v1/webhooks/calle", json={"run_id": "run_x"})
    assert res.status_code == 200
    assert res.json()["accepted"] is True
    assert res.json()["run_id"] == "run_x"


def test_webhook_fail_closed_missing_signature(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("CALLE_WEBHOOK_SECRET", "super-secret")
    get_settings.cache_clear()
    res = client.post("/v1/webhooks/calle", json={"run_id": "run_x"})
    assert res.status_code == 401
    get_settings.cache_clear()


def test_webhook_accepts_valid_hmac(client, monkeypatch):
    from app.config import get_settings

    secret = "super-secret"
    monkeypatch.setenv("CALLE_WEBHOOK_SECRET", secret)
    get_settings.cache_clear()
    content = b'{"run_id":"run_ok"}'
    digest = hmac.new(secret.encode(), content, hashlib.sha256).hexdigest()
    res = client.post(
        "/v1/webhooks/calle",
        content=content,
        headers={"Content-Type": "application/json", "X-Calle-Signature": f"sha256={digest}"},
    )
    assert res.status_code == 200
    assert res.json()["run_id"] == "run_ok"
    get_settings.cache_clear()
