import pytest
from jiralog.processor import (
    parse_issue_id,
    parse_task_text,
    format_time,
    group_laps,
    adjust_laps_to_full_minutes,
)


def test_parse_issue_id():
    assert parse_issue_id("PROJ-123 Development") == "PROJ-123"
    assert parse_issue_id("No issue here") is None


def test_parse_task_text():
    assert parse_task_text("PROJ-123 Development") == "Development"
    assert parse_task_text("PROJ-1 StandUp") == "StandUp"


def test_format_time():
    assert format_time(3600) == "01:00"
    assert format_time(5400) == "01:30"
    assert format_time(90) == "00:01"


def test_group_laps_merges_same_key():
    laps = [
        {"text": "PROJ-1 QA", "diff": 60000},
        {"text": "PROJ-1 QA", "diff": 120000},
        {"text": "PROJ-2 Dev", "diff": 60000},
    ]
    grouped, invalid = group_laps(laps)
    assert len(grouped) == 2
    assert len(invalid) == 0
    qa = next(l for l in grouped if "PROJ-1" in l["text"])
    assert qa["diff"] == 180000


def test_group_laps_invalid():
    laps = [{"text": "no issue key", "diff": 1000}]
    grouped, invalid = group_laps(laps)
    assert len(grouped) == 0
    assert len(invalid) == 1


def test_adjust_laps_no_deficit():
    # 60 seconds exactly — no rounding needed
    laps = [{"text": "PROJ-1 QA", "diff": 60000}]
    result = adjust_laps_to_full_minutes(laps)
    assert result[0]["diff"] == 60000


def test_adjust_laps_rounds_up():
    # Two laps: 90s + 90s = 180s = 3 min total
    # Each lap alone = 1 min (truncated) → deficit = 1
    laps = [
        {"text": "PROJ-1 QA",  "diff": 90000},
        {"text": "PROJ-2 Dev", "diff": 90000},
    ]
    result = adjust_laps_to_full_minutes(laps)
    total_minutes = sum((l["diff"] // 1000) // 60 for l in result)
    assert total_minutes == 3
