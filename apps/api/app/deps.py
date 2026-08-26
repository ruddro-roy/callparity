from app.config import get_settings
from app.fixtures.calle import FixtureCalle
from app.ports.calle import CallePort
from app.ports.live import LiveCalleSdk

_fixture = FixtureCalle()


def get_calle() -> CallePort:
    settings = get_settings()
    if settings.calle_mode == "fixture":
        return _fixture
    return LiveCalleSdk(settings.calle_base_url, token=settings.calle_api_token)


def get_live_reader() -> CallePort:
    """Reader for existing CALL-E call records, regardless of USE_FIXTURES.

    The import path only ever calls .get (GET /v1/calls/{id}). Without
    CALLE_API_TOKEN and CALLE_BASE_URL the adapter refuses before any
    request leaves the process, so a fixture-mode workbench stays offline.
    """
    settings = get_settings()
    return LiveCalleSdk(settings.calle_base_url, token=settings.calle_api_token)
