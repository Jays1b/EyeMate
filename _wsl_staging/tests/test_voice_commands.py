from services.voice_commands import (
    INTENT_CLIPBOARD,
    INTENT_COLOR,
    INTENT_HELP,
    INTENT_IDENTIFY,
    INTENT_NAVIGATE,
    INTENT_OCR,
    INTENT_PASTE,
    INTENT_PRODUCT,
    INTENT_SCENE,
    INTENT_SCREEN,
    INTENT_STOP,
    INTENT_UNKNOWN,
    parse_command,
)


def test_scene():
    for t in ["what is in front of me", "describe the scene", "what do you see"]:
        assert parse_command(t) == INTENT_SCENE

def test_ocr():
    for t in ["read this", "read the text", "ocr the document", "what does this label say"]:
        assert parse_command(t) == INTENT_OCR, t

def test_screen_priority_over_ocr():
    for t in ["read screen", "read the screen", "read the whole screen",
              "what does the screen say", "screen text", "read everything"]:
        assert parse_command(t) == INTENT_SCREEN, t
    # "read the text" must NOT be hijacked by the screen rule
    assert parse_command("read the text") == INTENT_OCR

def test_clipboard_and_paste():
    for t in ["read my clipboard", "clipboard", "read my last copy", "from clipboard",
              "read the copy buffer"]:
        assert parse_command(t) == INTENT_CLIPBOARD, t
    for t in ["paste text", "enter text", "type text", "read my text", "my own text"]:
        assert parse_command(t) == INTENT_PASTE, t
    assert parse_command("paste text") == INTENT_PASTE

def test_color():
    for t in ["what color", "what colour", "tell me the color of this"]:
        assert parse_command(t) == INTENT_COLOR, t

def test_product_priority_over_ocr():
    # "scan product" mentions 'product'; OCR rule must not win
    assert parse_command("scan product") == INTENT_PRODUCT
    assert parse_command("scan the barcode on this medicine") == INTENT_PRODUCT

def test_navigate():
    assert parse_command("help me navigate") == INTENT_NAVIGATE
    assert parse_command("is there anything in my way") == INTENT_NAVIGATE

def test_identify():
    assert parse_command("identify this") == INTENT_IDENTIFY

def test_help_stop():
    assert parse_command("help") == INTENT_HELP
    assert parse_command("stop talking") == INTENT_STOP

def test_unknown_and_empty():
    assert parse_command("") == INTENT_UNKNOWN
    assert parse_command("  ") == INTENT_UNKNOWN
    assert parse_command("gibberish words here") == INTENT_UNKNOWN

def test_case_and_whitespace_insensitive():
    assert parse_command("  WHAT   COLOR IS THIS  ") == INTENT_COLOR