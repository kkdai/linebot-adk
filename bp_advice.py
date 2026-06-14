"""Rule-based blood-pressure classification plus optional LLM polish.

Classification is deterministic (safety-critical); the wording can optionally be
made warmer by an LLM via the ``polish`` callback.
"""
from __future__ import annotations

import enum
from typing import Callable, Optional


class Category(enum.Enum):
    NORMAL = ("正常", False)
    ELEVATED = ("血壓偏高", False)
    STAGE1 = ("高血壓一期", False)
    STAGE2 = ("高血壓二期", False)
    CRISIS = ("高血壓危象", True)

    def __init__(self, label: str, is_urgent: bool):
        self.label = label
        self.is_urgent = is_urgent


# Base guidance per category (home-measurement oriented, general health info).
_BASE_GUIDANCE = {
    Category.NORMAL: "血壓很理想，請繼續保持規律作息與量測習慣。",
    Category.ELEVATED: "血壓略為偏高，建議留意飲食少鹽、規律運動，並持續每日量測。",
    Category.STAGE1: "已達高血壓一期，請持續記錄血壓，注意作息與飲食，並考慮諮詢醫師。",
    Category.STAGE2: "已達高血壓二期，建議盡快就醫評估並遵循醫囑用藥，避免劇烈活動。",
    Category.CRISIS: (
        "血壓非常高（高血壓危象）！請長輩立即坐下休息、不要激烈活動，"
        "若有頭痛、胸痛、呼吸困難或視力模糊等不適，請盡速就醫。"
    ),
}


def classify(systolic: int, diastolic: int) -> Category:
    """Classify a reading using standard home-measurement thresholds."""
    if systolic >= 180 or diastolic >= 120:
        return Category.CRISIS
    if systolic >= 140 or diastolic >= 90:
        return Category.STAGE2
    if systolic >= 130 or diastolic >= 80:
        return Category.STAGE1
    if 120 <= systolic <= 129 and diastolic < 80:
        return Category.ELEVATED
    return Category.NORMAL


# A polish callback takes (base_text, category) and returns a warmer rewrite.
PolishFn = Callable[[str, Category], str]


def build_advice(reading: dict, polish: Optional[PolishFn] = None) -> str:
    """Build the advice message for a reading.

    ``reading`` must contain ``systolic`` and ``diastolic`` (and optionally
    ``pulse``). If ``polish`` is given it rewrites the base text; on any failure
    we fall back to the deterministic base text.
    """
    systolic = reading["systolic"]
    diastolic = reading["diastolic"]
    pulse = reading.get("pulse")
    category = classify(systolic, diastolic)

    parts = [f"血壓 {systolic}/{diastolic}"]
    if pulse:
        parts.append(f"，脈搏 {pulse}")
    parts.append(f"\n分級：{category.label}\n{_BASE_GUIDANCE[category]}")
    base_text = "".join(parts)

    if polish is None:
        return base_text
    try:
        polished = polish(base_text, category)
        return polished or base_text
    except Exception:
        return base_text
