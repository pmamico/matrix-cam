"""Unit tests for ASCII conversion helpers."""

import numpy as np

from ascii_cam.ascii_renderer import ASCII_CHARS, AsciiFrame, ascii_preview, frame_to_ascii


def test_frame_to_ascii_maps_dark_and_light_pixels_bgr() -> None:
    frame = np.array(
        [
            [[0, 0, 0], [255, 255, 255]],
            [[128, 128, 128], [64, 64, 64]],
        ],
        dtype=np.uint8,
    )

    result = frame_to_ascii(frame, max_width=2, max_height=10)

    assert isinstance(result, AsciiFrame)
    assert len(result.rows) == 2
    assert result.rows[0][0] == ASCII_CHARS[0]
    assert result.rows[0][1] == ASCII_CHARS[-1]


def test_frame_to_ascii_rejects_non_bgr_input() -> None:
    frame = np.zeros((2, 2), dtype=np.uint8)

    try:
        frame_to_ascii(frame, max_width=2, max_height=2)
        raised = False
    except ValueError:
        raised = True

    assert raised


def test_frame_to_ascii_applies_foreground_mask() -> None:
    frame = np.full((2, 2, 3), 255, dtype=np.uint8)
    mask = np.array([[1, 0], [0, 1]], dtype=bool)

    result = frame_to_ascii(frame, max_width=2, max_height=10, foreground_mask=mask)

    assert result.rows[0][1] == " "
    assert result.rows[1][0] == " "
    assert result.mask is not None
    assert result.mask.sum() == 2


def test_ascii_preview_accepts_ascii_frame() -> None:
    frame = np.zeros((1, 1, 3), dtype=np.uint8)
    render = frame_to_ascii(frame, max_width=1, max_height=1)

    preview = ascii_preview(render, colored=False)

    assert preview.strip() == render.rows[0].strip()
