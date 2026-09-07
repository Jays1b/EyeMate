import numpy as np
import pytest

from services.color import classify_hsv, dominant_color, hsv_frame


def test_classify_hsv_basic():
    assert classify_hsv(0, 255, 200) == "red"
    assert classify_hsv(90, 255, 200) == "blue"
    assert classify_hsv(45, 255, 200) == "green"
    assert classify_hsv(20, 255, 200) == "orange"
    assert classify_hsv(30, 255, 200) == "yellow"

def test_classify_hsv_wrap_red():
    assert classify_hsv(179, 255, 200) == "red"
    assert classify_hsv(0, 255, 200) == "red"

def test_classify_hsv_dim():
    assert classify_hsv(0, 255, 5) == "black"
    assert classify_hsv(0, 0, 255) == "white"
    assert classify_hsv(0, 0, 100) == "gray"
    assert classify_hsv(0, 0, 40) == "dark gray"

@pytest.mark.parametrize("h,name", [
    (5, "red"), (15, "orange"), (30, "yellow"),
    (60, "green"), (90, "blue"), (140, "purple"),
])
def test_dominant_color_uniform(h, name):
    bgr = hsv_frame(h, 255, 180)
    props = dominant_color(bgr)
    assert props["name"] == name

def test_dominant_color_border_gray_center_chroma():
    bgr = hsv_frame(90, 255, 180, separate_chroma=1)
    props = dominant_color(bgr)
    assert props["name"] == "blue"

def test_dominant_color_black():
    bgr = hsv_frame(0, 0, 3)
    props = dominant_color(bgr)
    assert props["name"] == "black"

def test_dominant_color_white():
    bgr = hsv_frame(0, 0, 250)
    props = dominant_color(bgr)
    assert props["name"] == "white"

def test_dominant_color_bad_shape():
    with pytest.raises(ValueError):
        dominant_color(np.zeros((10, 10), dtype=np.uint8))

def test_dominant_color_unknown_not_crash():
    bgr = np.random.default_rng(0).integers(0, 255, size=(30, 30, 3), dtype=np.uint8)
    props = dominant_color(bgr)
    assert props["name"]