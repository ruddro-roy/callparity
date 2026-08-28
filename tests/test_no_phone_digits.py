"""No dialable number in the public surfaces: README, workbench copy, recorded calls.

Seed data and the ClaimKill skill fixtures deliberately carry fictional +1555
numbers that the app masks (mask_e164) and the skill validates and masks by
design, so they are out of scope here. This scan guards the surfaces that must
never carry a real, dialable number: the README a vendor reads, the UI copy a
dispatcher sees, and the recorded live-call bodies.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

E164 = re.compile(r"\+\d{7,15}")
LONG_DIGIT_RUN = re.compile(r"(?<!\d)\d{10,}(?!\d)")

TARGETS = [
    REPO / "README.md",
    *sorted((REPO / "apps" / "web" / "src").glob("*.jsx")),
    *sorted((REPO / "tests" / "fixtures").glob("*.json")),
]


def test_targets_exist():
    assert (REPO / "README.md") in TARGETS
    assert any(p.name == "App.jsx" for p in TARGETS)
    assert any(p.suffix == ".json" for p in TARGETS)


def test_no_dialable_phone_in_public_surfaces():
    for path in TARGETS:
        text = path.read_text(encoding="utf-8")
        assert not E164.search(text), f"E.164-shaped phone in {path.relative_to(REPO)}"
        assert not LONG_DIGIT_RUN.search(text), f"long digit run in {path.relative_to(REPO)}"
