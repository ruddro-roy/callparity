FR1842_A = {
    "structured_result": {
        "pallet_staged": True,
        "dock": "3",
        "at": "2026-08-23T06:40:00+06:00",
        "pallet_id": "PL-9F21",
        "driver_seen": True,
        "seal_number": None,
    },
    "transcript": (
        "North Gate, dock three. Yeah we rolled nine-foxtrot out of dock three "
        "around six forty. The jack was sitting on the yellow line. Seal number? "
        "I didn't look at the seal. Driver pulled in, we waved him toward three."
    ),
    "summary": "Warehouse asserts PL-9F21 staged at dock 3 at 06:40.",
}

FR1842_B = {
    "structured_result": {
        "arrived": True,
        "dock_pulled_to": "4",
        "saw_pallet_pl9f21": False,
        "dock_3_state": "empty",
        "waved_off_by": "yard marshal",
        "seal_number": None,
    },
    "transcript": (
        "I pulled to the North Gate at 06:38. Dock three was empty, they sent me "
        "to four. I never saw PL-9F21 on a jack. Yard marshal waved me off three."
    ),
    "summary": "Driver arrived; dock 3 empty; redirected to dock 4; pallet not seen.",
}

FR1900_A = {
    "structured_result": {
        "pallet_staged": True,
        "dock": "1",
        "at": "2026-08-23T07:10:00+06:00",
        "pallet_id": "PL-CTRL1",
        "driver_seen": True,
        "seal_number": "SL-88",
    },
    "transcript": "Control dock one. Pallet PL-CTRL1 is staged and the driver is hooked.",
    "summary": "Warehouse confirms staged pallet and hooked driver.",
}

FR1900_B = {
    "structured_result": {
        "arrived": True,
        "dock_pulled_to": "1",
        "saw_pallet_pl9f21": True,
        "pallet_id": "PL-CTRL1",
        "dock_3_state": "n/a",
        "seal_number": "SL-88",
    },
    "transcript": "I'm on door one. Pallet PL-CTRL1 is on the jack, seal SL-88, ready to roll.",
    "summary": "Driver confirms same pallet, same door, same seal.",
}

FR1888_A = {
    "structured_result": {
        "pallet_staged": True,
        "dock": "2",
        "at": "2026-08-23T08:05:00+06:00",
        "pallet_id": "PL-VM01",
        "driver_seen": False,
        "seal_number": None,
    },
    "transcript": (
        "Annex two. We staged PL-VM01 at dock two around eight oh five. "
        "Have not seen the driver yet."
    ),
    "summary": "Warehouse asserts PL-VM01 staged; driver not seen.",
}

FR1888_B = {
    "structured_result": {
        "unreachable": True,
        "disposition": "voicemail",
    },
    "transcript": "",
    "summary": "Party B went to voicemail. Silence is not confirmation.",
    "status": "voicemail",
}
