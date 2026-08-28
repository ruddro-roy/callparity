"""No E.164 reaches a log line, and the redactor leaves timestamps and ids intact."""

import structlog

from app.logging_conf import configure_logging, redact_log_value


def test_redacts_bare_and_formatted_e164():
    assert redact_log_value("+15550100001") == "[phone]"
    assert redact_log_value("dialing +1 (555) 010-0001 now") == "dialing [phone] now"


def test_leaves_timestamps_hashes_and_call_ids():
    assert redact_log_value("2026-08-28T11:09:21.321Z") == "2026-08-28T11:09:21.321Z"
    assert redact_log_value("call_vzro922bOACJjf19ML7vQQ") == "call_vzro922bOACJjf19ML7vQQ"
    assert redact_log_value(18000) == 18000


def test_processor_scrubs_every_string_field(capsys):
    configure_logging("INFO")
    structlog.get_logger("redaction-test").info("dial", to="+15550100001", note="ok")
    out = capsys.readouterr().out
    assert "+15550100001" not in out
    assert "[phone]" in out
    assert "ok" in out
