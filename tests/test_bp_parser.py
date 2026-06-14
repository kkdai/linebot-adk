import pytest

from bp_parser import parse_bp


@pytest.mark.parametrize(
    "text,expected",
    [
        ("120/80", {"systolic": 120, "diastolic": 80, "pulse": None}),
        ("120/80/70", {"systolic": 120, "diastolic": 80, "pulse": 70}),
        ("120 80 70", {"systolic": 120, "diastolic": 80, "pulse": 70}),
        ("120 80", {"systolic": 120, "diastolic": 80, "pulse": None}),
        ("血壓 120/80 脈搏 70", {"systolic": 120, "diastolic": 80, "pulse": 70}),
        ("收縮壓120 舒張壓80 脈搏70", {"systolic": 120, "diastolic": 80, "pulse": 70}),
        ("高壓 135 低壓 88", {"systolic": 135, "diastolic": 88, "pulse": None}),
        ("今天血壓是 145 / 95，脈搏 72", {"systolic": 145, "diastolic": 95, "pulse": 72}),
    ],
)
def test_parse_valid(text, expected):
    assert parse_bp(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "你好",
        "今天天氣很好",
        "謝謝",
        "120",  # single number is not a BP reading
        "",
    ],
)
def test_parse_non_bp(text):
    assert parse_bp(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "20/10",     # systolic too low
        "400/200",   # systolic too high
        "120/250",   # diastolic too high
        "80/120",    # systolic must exceed diastolic
    ],
)
def test_parse_out_of_range(text):
    assert parse_bp(text) is None


def test_pulse_out_of_range_dropped():
    # implausible pulse is dropped, BP still parsed
    assert parse_bp("120/80/500") == {"systolic": 120, "diastolic": 80, "pulse": None}
