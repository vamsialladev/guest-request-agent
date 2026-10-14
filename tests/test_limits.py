import json

from src.limits import DailyCounter


def test_daily_cap_is_enforced_and_survives_a_new_session(tmp_path):
    path = tmp_path / "daily.json"
    first = DailyCounter(path, limit=2, today=lambda: "2026-10-09")
    assert first.try_consume() and first.try_consume()
    assert not first.try_consume()
    # A page refresh or another visitor creates a new counter object: the cap still holds.
    second = DailyCounter(path, limit=2, today=lambda: "2026-10-09")
    assert second.used() == 2 and not second.try_consume()


def test_cap_resets_on_a_new_day(tmp_path):
    path = tmp_path / "daily.json"
    DailyCounter(path, limit=1, today=lambda: "2026-10-09").try_consume()
    tomorrow = DailyCounter(path, limit=1, today=lambda: "2026-10-10")
    assert tomorrow.used() == 0 and tomorrow.try_consume()


def test_damaged_counter_file_starts_from_zero(tmp_path):
    path = tmp_path / "daily.json"
    path.write_text("{not json", encoding="utf-8")
    counter = DailyCounter(path, limit=5, today=lambda: "2026-10-09")
    assert counter.used() == 0 and counter.try_consume()
    assert json.loads(path.read_text(encoding="utf-8")) == {"date": "2026-10-09", "count": 1}


def test_zero_limit_blocks_everything(tmp_path):
    assert not DailyCounter(tmp_path / "d.json", limit=0).try_consume()
