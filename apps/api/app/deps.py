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
