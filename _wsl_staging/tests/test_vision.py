import os

from services.vision import Detector, filter_detections, iou, load_labels, nms


def test_load_labels(tmp_path):
    p = tmp_path / "labels.txt"
    p.write_text("person\nbicycle: foo\n car \n\n dog\n", encoding="utf-8")
    labels = load_labels(str(p))
    assert labels == ["person", "bicycle", "car", "dog"]


def test_load_labels_missing():
    assert load_labels("nope.txt") == []


def test_filter_detections_threshold():
    boxes = [[0.1, 0.1, 0.5, 0.5], [0.2, 0.2, 0.6, 0.6], [0, 0, 1, 1]]
    scores = [0.9, 0.4, 0.7]
    classes = [1, 1, 2]
    out = filter_detections(boxes, scores, classes, 0.5)
    assert len(out) == 2
    assert out[0]["label_index"] == 1
    assert out[1]["score"] == 0.7


def test_iou():
    a = [0, 0, 10, 10]
    b = [5, 0, 15, 10]
    assert abs(iou(a, b) - 0.333) < 0.01
    assert iou(a, a) == 1.0
    assert iou([0, 0, 1, 1], [2, 2, 3, 3]) == 0.0


def test_nms_removes_overlap_same_class():
    dets = [
        {"label_index": 1, "score": 0.9, "box": [0, 0, 10, 10]},
        {"label_index": 1, "score": 0.8, "box": [1, 1, 11, 11]},
        {"label_index": 1, "score": 0.7, "box": [30, 30, 40, 40]},
    ]
    kept = nms(dets, iou_threshold=0.45)
    assert len(kept) == 2


def test_nms_keeps_different_classes():
    dets = [
        {"label_index": 1, "score": 0.9, "box": [0, 0, 10, 10]},
        {"label_index": 2, "score": 0.8, "box": [1, 1, 11, 11]},
    ]
    kept = nms(dets, iou_threshold=0.45)
    assert len(kept) == 2


def test_detector_without_model_is_graceful():
    det = Detector(model_path="missing.tflite")
    assert det.available is False
    assert det.run(None) == []
    assert det.run(__import__("numpy").zeros((10, 10, 3), dtype="uint8")) == []