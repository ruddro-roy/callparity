import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
API_ROOT = REPO / "apps" / "api"
sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(REPO / "scripts"))

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_callparity.db")
os.environ.setdefault("REDIS_OPTIONAL", "true")
os.environ.setdefault("USE_FIXTURES", "true")
os.environ.setdefault("SEED_ON_STARTUP", "false")
os.environ.setdefault("PLAYBACK_DELAY_MS", "0")
os.environ.setdefault("OPERATOR_TOKEN", "test-operator-token")
# Effectively unlimited so unrelated tests never trip the limiter;
# tests/test_rate_limit.py builds its own client with a small budget.
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000000")

OPERATOR_TOKEN = os.environ["OPERATOR_TOKEN"]
AUTH = {"Authorization": f"Bearer {OPERATOR_TOKEN}"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db}")
    monkeypatch.setenv("REDIS_OPTIONAL", "true")
    monkeypatch.setenv("SEED_ON_STARTUP", "false")
    monkeypatch.setenv("USE_FIXTURES", "true")
    monkeypatch.setenv("PLAYBACK_DELAY_MS", "0")
    monkeypatch.setenv("OPERATOR_TOKEN", OPERATOR_TOKEN)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000000")

    from app.config import get_settings
    from app.db import init_db, reset_engine
    from app.ratelimit import reset_rate_limiter

    get_settings.cache_clear()
    reset_engine()
    reset_rate_limiter()
    init_db()
    from seed_demo_data import seed

    seed()
    from app.main import app

    with TestClient(app) as c:
        c.headers.update(AUTH)
        yield c
    reset_engine()
    get_settings.cache_clear()
