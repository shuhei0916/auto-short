import json
from datetime import datetime, timezone

from autoshort.schedule import next_seed, next_slots, taken_slots, to_rfc3339

UTC = timezone.utc


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def test_slots_are_the_next_configured_hours():
    assert next_slots(at(12, 10), 3, hours=(15, 23)) == [at(12, 15), at(12, 23), at(13, 15)]


def test_slot_too_close_to_now_is_skipped():
    # YouTube needs time to process; anything within the margin moves to the next slot.
    assert next_slots(at(12, 14, 30), 1, hours=(15, 23)) == [at(12, 23)]


def test_already_taken_slots_are_skipped():
    assert next_slots(at(12, 10), 2, hours=(15, 23), taken={at(12, 15), at(12, 23)}) == [
        at(13, 15),
        at(13, 23),
    ]


def test_rfc3339_format_is_what_youtube_expects():
    assert to_rfc3339(at(12, 15)) == "2026-11-12T15:00:00Z"


def _meta(d, seed, publish_at=None, uploaded=True):
    up = {"publish_at": publish_at} if uploaded else None
    (d / f"ring_escape_{seed:05d}.json").write_text(json.dumps({"seed": seed, "uploaded": up}))


def test_next_seed_follows_the_highest_used(tmp_path):
    assert next_seed(tmp_path) == 1
    _meta(tmp_path, 3)
    _meta(tmp_path, 7, uploaded=False)
    assert next_seed(tmp_path) == 8


def test_taken_slots_come_from_uploaded_metadata(tmp_path):
    _meta(tmp_path, 1, "2026-11-12T15:00:00Z")
    _meta(tmp_path, 2, None)
    _meta(tmp_path, 3, uploaded=False)
    assert taken_slots(tmp_path) == {at(12, 15)}
