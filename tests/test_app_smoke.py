import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(os.environ.get("EYEMATE_SKIP_UI") == "1", reason="headless")
def test_main_module_imports():
    import main  # noqa: F401


@pytest.mark.skipif(os.environ.get("EYEMATE_SKIP_UI") == "1", reason="headless")
def test_kv_compiles():
    from kivy.lang import Builder

    path = os.path.join(ROOT, "main.kv")
    Builder.load_file(path)


def test_help_text_mentions_features():
    from services.speech import help_text

    text = help_text()
    for word in ("in front", "read text", "color", "product"):
        assert word.lower() in text.lower()