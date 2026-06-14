from bp_image import extract_bp_from_image


def _gen(text):
    return lambda image_bytes, mime_type: text


def test_extract_clean_json():
    out = extract_bp_from_image(b"img", generate=_gen('{"systolic":135,"diastolic":85,"pulse":72}'))
    assert out == {"systolic": 135, "diastolic": 85, "pulse": 72}


def test_extract_json_with_surrounding_text():
    out = extract_bp_from_image(
        b"img", generate=_gen('好的 {"systolic":120,"diastolic":80,"pulse":null} 以上')
    )
    assert out == {"systolic": 120, "diastolic": 80, "pulse": None}


def test_extract_unreadable_returns_none():
    out = extract_bp_from_image(
        b"img", generate=_gen('{"systolic":null,"diastolic":null,"pulse":null}')
    )
    assert out is None


def test_extract_out_of_range_returns_none():
    out = extract_bp_from_image(b"img", generate=_gen('{"systolic":400,"diastolic":85,"pulse":72}'))
    assert out is None


def test_extract_bad_json_returns_none():
    assert extract_bp_from_image(b"img", generate=_gen("not json at all")) is None


def test_extract_implausible_pulse_dropped():
    out = extract_bp_from_image(b"img", generate=_gen('{"systolic":120,"diastolic":80,"pulse":5}'))
    assert out == {"systolic": 120, "diastolic": 80, "pulse": None}


def test_extract_generate_error_returns_none():
    def boom(image_bytes, mime_type):
        raise RuntimeError("api down")

    assert extract_bp_from_image(b"img", generate=boom) is None
