import inspect

from app.fixtures.calle import FixtureCalle
from app.ports.calle import CallePort, CallTask


def test_fixture_covers_every_calleport_method():
    required = {name for name, _ in inspect.getmembers(CallePort, predicate=callable) if not name.startswith("_")}
    required = {"plan", "run", "get", "ping"}
    for name in required:
        assert hasattr(FixtureCalle, name)
        assert callable(getattr(FixtureCalle, name))


def test_use_fixtures_true_and_false_select_adapter(monkeypatch):
    from app.config import get_settings
    from app.deps import get_calle
    from app.fixtures.calle import FixtureCalle
    from app.ports.live import LiveCalleSdk

    monkeypatch.setenv("USE_FIXTURES", "true")
    get_settings.cache_clear()
    assert isinstance(get_calle(), FixtureCalle)

    monkeypatch.setenv("USE_FIXTURES", "false")
    get_settings.cache_clear()
    adapter = get_calle()
    assert isinstance(adapter, LiveCalleSdk)
    get_settings.cache_clear()


def test_fixture_plan_run_get_ping_roundtrip():
    calle = FixtureCalle()
    assert calle.ping() is True
    plan = calle.plan(CallTask(ticket_id="FR-1842", party_role="A", to_phones=["+15550100001"], goal="g", consent=True))
    run = calle.run(plan)
    view = calle.get(run)
    assert view.status == "completed"
    assert view.transcript
