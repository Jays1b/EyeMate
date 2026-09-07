from services.ocr import clean_text, summarize_medication


def test_clean_text_collapse_newlines():
    raw = "Take one tablet\ndaily.\n\n   With water  "
    assert clean_text(raw) == "Take one tablet daily. With water"

def test_clean_text_spaced_out():
    raw = "D O C T O R   S M I T H"
    assert clean_text(raw) == "DOCTOR SMITH"

def test_clean_text_removes_barcode_digits():
    raw = "12345678901\nAspirin 81 mg"
    out = clean_text(raw)
    assert "12345678901" not in out
    assert "Aspirin" in out

def test_clean_text_punctuation_kept():
    out = clean_text("Take: one (adult) tablet -- at bedtime!")
    assert ":" in out and "(" in out and ")" in out

def test_clean_text_empty():
    assert clean_text("") == ""
    assert clean_text(None) == ""

def test_medication_summary_prefers_dose_lines():
    lines = [
        "Lorem ipsum dolor sit amet consectetur",
        "Take one 500 mg tablet twice daily after food",
        "Do not take on an empty stomach",
    ]
    out = summarize_medication(lines)
    assert "500 mg" in out
    assert "after food" in out

def test_medication_summary_truncates():
    long_line = "Very long line " * 50
    out = summarize_medication([long_line], max_chars=60)
    assert len(out) <= 64

def test_medication_summary_empty():
    assert summarize_medication([]) == ""