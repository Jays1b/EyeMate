import sys
from unittest.mock import MagicMock

import numpy as np
import pytest

from services.vision import Detector


def _monkeypatch_interp(monkeypatch, interp):
    monkeypatch.setattr("services.vision._INTERPRETER_CLS", lambda **k: interp)


class FakeInterp:
    def __init__(self, boxes, classes, scores, num):
        self._boxes = np.array(boxes, dtype=np.float32)
        self._classes = np.array(classes, dtype=np.float32)
        self._scores = np.array(scores, dtype=np.float32)
        self._num = np.array([num], dtype=np.float32)
        self._in = {"index": 0, "shape": [1, 300, 300, 3], "dtype": np.float32}

    def allocate_tensors(self):
        pass

    def get_input_details(self):
        return [self._in]

    def get_output_details(self):
        return [
            {"name": "TFLite_Detection_PostProcess", "index": 100},
            {"name": "TFLite_Detection_PostProcess:1", "index": 101},
            {"name": "TFLite_Detection_PostProcess:2", "index": 102},
            {"name": "TFLite_Detection_PostProcess:3", "index": 103},
        ]

    def get_tensor(self, index):
        return {
            100: self._boxes[None],
            101: self._classes[None],
            102: self._scores[None],
            103: self._num,
        }[index]

    def set_tensor(self, *a, **k):
        pass

    def invoke(self):
        pass


def _monkeypatch_interp(monkeypatch, interp):
    monkeypatch.setattr("services.vision._INTERPRETER_CLS", lambda **k: interp)


def test_detector_run_pipeline(monkeypatch, tmp_path):
    model = tmp_path / "m.tflite"
    model.write_bytes(b"fake")
    labels = tmp_path / "l.txt"
    labels.write_text("0: ???\n1: person\n2: bicycle\n3: car\n", encoding="utf-8")

    interp = FakeInterp(
        boxes=[[0.1, 0.1, 0.6, 0.6], [0.2, 0.2, 0.8, 0.8], [0.5, 0.5, 0.9, 0.9]],
        classes=[1, 1, 3],
        scores=[0.95, 0.3, 0.6],
        num=3,
    )
    _monkeypatch_interp(monkeypatch, interp)

    det = Detector(model_path=str(model), labels_path=str(labels))
    res = det.run(np.zeros((200, 200, 3), dtype=np.uint8), score_threshold=0.5)
    # two kept after NMS (person + car), low-score person dropped
    labels_out = sorted(r["label"] for r in res)
    assert labels_out == ["car", "person"]


def test_detector_run_positional_fallback(monkeypatch, tmp_path):
    model = tmp_path / "m.tflite"
    model.write_bytes(b"fake")
    labels = tmp_path / "l.txt"
    labels.write_text("0: ???\n1: person\n2: bicycle\n", encoding="utf-8")

    # Name-less outputs to force positional fallback.
    class PosInterp(FakeInterp):
        def get_output_details(self):
            return [{"name": "a", "index": 100}, {"name": "b", "index": 101},
                    {"name": "c", "index": 102}, {"name": "d", "index": 103}]

    interp = PosInterp(boxes=[[0, 0, 1, 1]], classes=[1], scores=[0.9], num=1)
    _monkeypatch_interp(monkeypatch, interp)

    det = Detector(model_path=str(model), labels_path=str(labels))
    res = det.run(np.zeros((100, 100, 3), dtype=np.uint8), score_threshold=0.5)
    assert res and res[0]["label"] == "person"