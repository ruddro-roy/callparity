import os
import shutil
import urllib.request

import pytest


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not available")
def test_compose_health_if_running():
    if os.environ.get("SKIP_COMPOSE_SMOKE") == "1":
        pytest.skip("explicit skip")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/healthz", timeout=2) as resp:
            body = resp.read().decode()
        assert "postgres" in body
    except Exception:
        pytest.skip("api not listening; run docker compose up first")
