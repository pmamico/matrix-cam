"""Unit tests for the segmentation helpers."""

import numpy as np

from ascii_cam.segmentation import ForegroundSegmenter, SegmentationConfig, SegmentationError


def test_foreground_segmenter_rejects_invalid_backend() -> None:
    try:
        ForegroundSegmenter(SegmentationConfig(backend="does-not-exist"))
        raised = False
    except SegmentationError:
        raised = True

    assert raised


def test_foreground_segmenter_returns_boolean_mask() -> None:
    segmenter = ForegroundSegmenter(SegmentationConfig(history=5, kernel_size=1))

    black = np.zeros((8, 8, 3), dtype=np.uint8)
    segmenter.compute_mask(black)  # Prime the background subtractor
    bright = np.full((8, 8, 3), 255, dtype=np.uint8)

    mask = segmenter.compute_mask(bright)

    assert mask.shape == (8, 8)
    assert mask.dtype == np.bool_
