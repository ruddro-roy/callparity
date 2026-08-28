"""No E.164 reaches a log line, and the redactor leaves timestamps and ids intact.

The sample is built from parts so no phone-shaped literal appears in this file.
"""

import structlog
from app.logging_conf import configure_logging, redact_log_value

# Synthetic E.164-shaped run, assembled at runtime; never a real, dialable number.
SAMPLE = "+1" + "5" * 10


def test_redacts_bare_and_formatted_e164():
    assert redact_log_value(SAMPLE) == "[phone]"
    assert redact_log_value(f"dialing {SAMPLE} now") == "dialing [phone] now"


def test_leaves_timestamps_hashes_and_call_ids():
    assert redact_log_value("2026-08-28T11:09:21.321Z") == "2026-08-28T11:09:21.321Z"
    assert redact_log_value("call_vzro922bOACJjf19ML7vQQ") == "call_vzro922bOACJjf19ML7vQQ"
    assert redact_log_value(18000) == 18000


def test_redacts_nested_dicts_and_lists():
    nested = {"parties": [{"phone": SAMPLE}, {"phone": "clean"}], "note": "ok"}
    red = redact_log_value(nested)
    assert red["parties"][0]["phone"] == "[phone]"
    assert red["parties"][1]["phone"] == "clean"
    assert red["note"] == "ok"


def test_processor_scrubs_every_string_field(capsys):
    configure_logging("INFO")
    structlog.get_logger("redaction-test").info("dial", to=SAMPLE, note="ok")
    out = capsys.readouterr().out
    assert SAMPLE not in out
    assert "[phone]" in out
    assert "ok" in out
