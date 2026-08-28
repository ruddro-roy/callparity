from __future__ import annotations

import sys
from pathlib import Path

# Allow `python scripts/seed_demo_data.py` from repo root or container /app
ROOTS = [
    Path(__file__).resolve().parent.parent / "apps" / "api",
    Path("/app"),
    Path(__file__).resolve().parent.parent,
]
for root in ROOTS:
    if (root / "app").exists() and str(root) not in sys.path:
        sys.path.insert(0, str(root))

from app.db import init_db, session_factory
from app.models.orm import TicketRow
from sqlalchemy.orm import Session

FR1842 = {
    "id": "FR-1842",
    "domain": "cold_chain_freight",
    "fact": "Where is pallet PL-9F21 and can the truck leave loaded?",
    "entities": {
        "pallet_id": "PL-9F21",
        "sku": "insulin-cartridge-40",
        "temp_band_c": [2, 8],
    },
    "parties": [
        {
            "role": "A",
            "label": "North Gate Warehouse",
            "phone_e164": "+15550100001",
            "consent": True,
        },
        {
            "role": "B",
            "label": "Driver - fleet 441",
            "phone_e164": "+15550100002",
            "consent": True,
        },
    ],
    "sla_usd_per_hour": 18000,
}

FR1900 = {
    "id": "FR-1900",
    "domain": "cold_chain_freight",
    "fact": "Confirm pallet PL-CTRL1 is staged and the truck can release.",
    "entities": {
        "pallet_id": "PL-CTRL1",
        "sku": "insulin-cartridge-40",
        "temp_band_c": [2, 8],
    },
    "parties": [
        {
            "role": "A",
            "label": "South Annex",
            "phone_e164": "+15550100003",
            "consent": True,
        },
        {
            "role": "B",
            "label": "Driver - fleet 118",
            "phone_e164": "+15550100004",
            "consent": True,
        },
    ],
    "sla_usd_per_hour": 4000,
}

FR1888 = {
    "id": "FR-1888",
    "domain": "cold_chain_freight",
    "fact": "Where is pallet PL-VM01 after the driver went to voicemail?",
    "entities": {
        "pallet_id": "PL-VM01",
        "sku": "insulin-cartridge-40",
        "temp_band_c": [2, 8],
    },
    "parties": [
        {
            "role": "A",
            "label": "West Annex",
            "phone_e164": "+15550100005",
            "consent": True,
        },
        {
            "role": "B",
            "label": "Driver - fleet 902 (voicemail)",
            "phone_e164": "+15550100006",
            "consent": True,
        },
    ],
    "sla_usd_per_hour": 9000,
}


def seed(session: Session | None = None) -> None:
    own = False
    if session is None:
        init_db()
        session = session_factory()()
        own = True
    for payload in (FR1842, FR1900, FR1888):
        if session.get(TicketRow, payload["id"]) is None:
            session.add(TicketRow(**payload))
    session.commit()
    if own:
        session.close()


if __name__ == "__main__":
    seed()
    print("seeded FR-1842, FR-1900, and FR-1888")
