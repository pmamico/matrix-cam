"""Prototype script converting a single camera frame into ASCII art."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from .ascii_renderer import CHAR_ASPECT_RATIO, ascii_preview, frame_to_ascii
from .camera import CameraError, CameraStream
from .segmentation import ForegroundSegmenter, SegmentationConfig, SegmentationError


def main() -> None:
    args = _parse_args()
    segmenter = _build_segmenter(args)
    frame = _capture_frame()

    if args.save_frame:
        _save_frame(frame, args.save_frame)

    mask = segmenter.compute_mask(frame) if segmenter else None
    render_height = max(1, int(args.height / CHAR_ASPECT_RATIO))
    ascii_frame = frame_to_ascii(
        frame,
        max_width=args.width,
        max_height=render_height,
        foreground_mask=mask,
    )
    print(ascii_preview(ascii_frame, colored=not args.no_color))

    if args.stats:
        stats = _calc_stats(frame)
        print(
            f"\nFrame stats: shape={stats['shape']} min={stats['min']} max={stats['max']} "
            f"mean={stats['mean']:.2f} std={stats['std']:.2f}"
        )
        if ascii_frame.mask is not None:
            print(f"Foreground coverage: {ascii_frame.foreground_ratio * 100:.1f}%")

    if segmenter:
        segmenter.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=120, help="ASCII output width")
    parser.add_argument("--height", type=int, default=60, help="ASCII output height")
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Display frame statistics (shape, min/max, mean, std)",
    )
    parser.add_argument(
        "--save-frame",
        type=Path,
        help="Save the captured BGR frame as PNG for inspection",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in the preview output",
    )
    parser.add_argument(
        "--segment",
        action="store_true",
        help="Apply foreground masking before rendering",
    )
    parser.add_argument(
        "--segment-backend",
        choices=ForegroundSegmenter.available_backends(),
        default="mog2",
        help="Segmentation backend to use",
    )
    parser.add_argument(
        "--segment-confidence",
        type=float,
        default=0.3,
        help="Confidence threshold for ML-based segmentation",
    )
    return parser.parse_args()


def _capture_frame() -> np.ndarray:
    try:
        with CameraStream() as camera:
            frame = camera.read_frame()
    except CameraError as err:
        raise SystemExit(f"Camera error: {err}")
    return frame


def _save_frame(frame: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(path), frame)
    if not success:
        raise SystemExit(f"Failed to save frame to {path}")


def _calc_stats(frame: np.ndarray) -> dict[str, float | tuple[int, int]]:
    return {
        "shape": frame.shape[:2],
        "min": float(frame.min()),
        "max": float(frame.max()),
        "mean": float(frame.mean()),
        "std": float(frame.std()),
    }


if __name__ == "__main__":
    main()

def _build_segmenter(args: argparse.Namespace) -> ForegroundSegmenter | None:
    if not args.segment:
        return None
    config = SegmentationConfig(
        backend=args.segment_backend,
        min_confidence=args.segment_confidence,
    )
    try:
        return ForegroundSegmenter(config)
    except SegmentationError as err:
        raise SystemExit(f"Segmentation setup failed: {err}")
