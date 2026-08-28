import logging
import re
import sys
from typing import Any

import structlog

# E.164-shaped runs only (leading +). ISO timestamps and hashes have no +, so
# the safety net never mangles them.
_LOG_PHONE = re.compile(r"\+\d[\d\s().\-]{6,}\d")


def mask_e164(value: str) -> str:
    if value.startswith("+") and len(value) >= 8:
        return value[:5] + "***" + value[-4:]
    return value


def redact_log_value(value: Any) -> Any:
    """Recursively scrub E.164-shaped runs from strings, nested dicts, and lists."""
    if isinstance(value, str):
        return _LOG_PHONE.sub("[phone]", value)
    if isinstance(value, dict):
        return {k: redact_log_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(redact_log_value(v) for v in value)
    return value


def _redact_phones_processor(_logger: Any, _name: str, event_dict: dict) -> dict:
    """Last line of defense: no E.164 reaches stdout even if a call site forgets to mask."""
    for key, value in event_dict.items():
        event_dict[key] = redact_log_value(value)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _redact_phones_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), stream=sys.stdout)
