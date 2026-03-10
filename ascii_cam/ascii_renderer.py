"""Utilities for turning camera frames into Matrix-style ASCII art."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

import cv2
import numpy as np

ASCII_CHARS: Sequence[str] = tuple(chr(code) for code in range(32, 127))
CHAR_ASPECT_RATIO = 0.45  # Character cells are taller than they are wide.


@dataclass(slots=True)
class AsciiFrame:
    rows: List[str]
    mask: Optional[np.ndarray]
    width: int
    height: int
    foreground_ratio: float


def frame_to_ascii(
    bgr_frame: np.ndarray,
    max_width: int,
    max_height: int,
    charset: Sequence[str] = ASCII_CHARS,
    foreground_mask: Optional[np.ndarray] = None,
) -> AsciiFrame:
    if bgr_frame.ndim != 3 or bgr_frame.shape[2] != 3:
        raise ValueError("Input frame must be a BGR image")
    if max_width <= 0 or max_height <= 0:
        raise ValueError("max_width and max_height must be positive")
    if foreground_mask is not None and foreground_mask.shape[:2] != bgr_frame.shape[:2]:
        raise ValueError("foreground_mask must match the input frame size")

    frame_height, frame_width = bgr_frame.shape[:2]
    target_width = max(1, min(max_width, frame_width))
    adjusted_height = int(max_height * CHAR_ASPECT_RATIO)
    target_height = max(1, min(adjusted_height, frame_height))

    interpolation = _choose_interpolation(bgr_frame, target_width, target_height)

    gray_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
    gray_resized = cv2.resize(
        gray_frame,
        (target_width, target_height),
        interpolation=interpolation,
    )

    normalized = gray_resized.astype(np.float32) / 255.0
    scaled = np.clip((normalized * (len(charset) - 1)).astype(np.int32), 0, len(charset) - 1)
    charset_array = np.array(charset, dtype="<U1")
    ascii_rows = ["".join(charset_array[row].tolist()) for row in scaled]

    if foreground_mask is not None:
        reduced_mask = _resize_mask(foreground_mask, target_width, target_height)
        ascii_rows = _apply_mask(ascii_rows, reduced_mask)
    else:
        reduced_mask = None

    padded_rows = [row.ljust(max_width)[:max_width] for row in ascii_rows]
    padded_mask = _pad_mask(reduced_mask, target_height, max_width)
    foreground_ratio = (
        float(padded_mask.sum()) / padded_mask.size if padded_mask is not None else 0.0
    )
    return AsciiFrame(
        rows=padded_rows,
        mask=padded_mask,
        width=max_width,
        height=len(padded_rows),
        foreground_ratio=foreground_ratio,
    )


def ascii_preview(rows: Iterable[str] | AsciiFrame, colored: bool = True) -> str:
    if isinstance(rows, AsciiFrame):
        text_rows = rows.rows
    else:
        text_rows = list(rows)
    text = "\n".join(text_rows)
    if colored:
        return f"\033[32m{text}\033[0m"
    return text


def _choose_interpolation(frame: np.ndarray, target_width: int, target_height: int) -> int:
    shrinking = target_width < frame.shape[1] or target_height < frame.shape[0]
    very_small_target = target_width <= 2 or target_height <= 2

    if shrinking and not very_small_target:
        return cv2.INTER_AREA
    return cv2.INTER_NEAREST


def _resize_mask(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    if mask.ndim == 3:
        mask_2d = mask[:, :, 0]
    else:
        mask_2d = mask
    mask_float = mask_2d.astype(np.float32)
    resized = cv2.resize(mask_float, (width, height), interpolation=cv2.INTER_NEAREST)
    return resized > 0.5


def _apply_mask(rows: List[str], mask: np.ndarray) -> List[str]:
    masked_rows: List[str] = []
    for row_chars, mask_row in zip(rows, mask):
        chars = list(row_chars)
        for idx, keep in enumerate(mask_row):
            if idx >= len(chars):
                break
            if not keep:
                chars[idx] = " "
        masked_rows.append("".join(chars))
    return masked_rows


def _pad_mask(mask: Optional[np.ndarray], height: int, width: int) -> Optional[np.ndarray]:
    if mask is None:
        return None
    padded = np.zeros((height, width), dtype=bool)
    mask_height, mask_width = mask.shape[:2]
    padded[:mask_height, :mask_width] = mask
    return padded
