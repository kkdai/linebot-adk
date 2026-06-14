"""Read a blood-pressure reading from a photo of a monitor using Gemini.

The model call is injectable (``generate``) so the parsing/validation logic can
be unit-tested without hitting the API.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

from bp_parser import BPReading, _valid_bp, _clean_pulse

MODEL = "gemini-2.5-flash"

_PROMPT = (
    "你是血壓計讀數辨識助手。請看這張血壓計照片，只輸出 JSON，"
    '格式為 {"systolic": 收縮壓, "diastolic": 舒張壓, "pulse": 脈搏或null}。'
    "systolic 是較大的數字（高壓），diastolic 是較小的數字（低壓）。"
    "若無法辨識任何數字，輸出 {\"systolic\": null, \"diastolic\": null, \"pulse\": null}。"
    "不要輸出任何其他文字。"
)

# A generate function takes (image_bytes, mime_type) and returns the model text.
GenerateFn = Callable[[bytes, str], str]


def _parse_model_json(text: str) -> Optional[dict]:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def extract_bp_from_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    *,
    generate: Optional[GenerateFn] = None,
) -> Optional[BPReading]:
    """Return a validated reading from the image, or None if unreadable."""
    gen = generate or _default_generate
    try:
        text = gen(image_bytes, mime_type)
    except Exception:
        return None

    data = _parse_model_json(text)
    if not data:
        return None

    systolic = data.get("systolic")
    diastolic = data.get("diastolic")
    if not isinstance(systolic, int) or not isinstance(diastolic, int):
        return None
    if not _valid_bp(systolic, diastolic):
        return None

    pulse = data.get("pulse")
    pulse = pulse if isinstance(pulse, int) else None
    return {
        "systolic": systolic,
        "diastolic": diastolic,
        "pulse": _clean_pulse(pulse),
    }


def _default_generate(image_bytes: bytes, mime_type: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client()
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            _PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
    )
    return response.text or ""
