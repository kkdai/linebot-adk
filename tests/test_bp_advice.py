import bp_advice
from bp_advice import classify, Category, build_advice


def test_classify_boundaries():
    assert classify(115, 75) == Category.NORMAL
    assert classify(119, 79) == Category.NORMAL
    assert classify(120, 79) == Category.ELEVATED
    assert classify(129, 79) == Category.ELEVATED
    assert classify(130, 79) == Category.STAGE1
    assert classify(120, 80) == Category.STAGE1  # diastolic pushes up
    assert classify(139, 89) == Category.STAGE1
    assert classify(140, 85) == Category.STAGE2
    assert classify(135, 90) == Category.STAGE2
    assert classify(180, 100) == Category.CRISIS
    assert classify(160, 120) == Category.CRISIS


def test_crisis_flag():
    assert Category.CRISIS.is_urgent is True
    assert Category.STAGE2.is_urgent is False


def test_build_advice_without_llm_contains_numbers_and_label():
    reading = {"systolic": 185, "diastolic": 100, "pulse": 88}
    text = build_advice(reading, polish=None)
    assert "185" in text and "100" in text
    assert Category.CRISIS.label in text
    assert "就醫" in text or "休息" in text  # urgent guidance present


def test_build_advice_normal():
    reading = {"systolic": 118, "diastolic": 76, "pulse": 70}
    text = build_advice(reading, polish=None)
    assert Category.NORMAL.label in text
    assert "118" in text


def test_build_advice_uses_polish_callback():
    reading = {"systolic": 118, "diastolic": 76, "pulse": None}
    called = {}

    def fake_polish(base_text, category):
        called["base"] = base_text
        called["category"] = category
        return "潤飾後文字"

    out = build_advice(reading, polish=fake_polish)
    assert out == "潤飾後文字"
    assert called["category"] == Category.NORMAL
    assert "118" in called["base"]
