"""Application entry point for the curses-based ASCII camera."""

from __future__ import annotations

import argparse
import curses
from pathlib import Path
from typing import Sequence

from .segmentation import ForegroundSegmenter
from .ui import UIOptions, run_ui


def run(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.video:
        sources: tuple[int | str, ...] = (str(args.video),)
    else:
        sources = tuple(args.source)
    options = UIOptions(
        refresh_delay=args.refresh_delay,
        start_segmentation=not args.no_mask,
        segmentation_backend=args.segment_backend,
        camera_sources=sources,
    )
    curses.wrapper(run_ui, options)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Real-time ASCII camera viewer. "
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--refresh-delay",
        type=float,
        default=0.03,
        help="Seconds between frame renders (lower is faster, higher uses less CPU)",
    )
    parser.add_argument(
        "--no-mask",
        action="store_true",
        help="Start with the foreground mask disabled",
    )
    parser.add_argument(
        "--segment-backend",
        choices=ForegroundSegmenter.available_backends(),
        default="mog2",
        help="Select the segmentation backend",
    )
    parser.add_argument(
        "--source",
        type=int,
        nargs="+",
        metavar="INDEX",
        default=None,
        help="Camera source to use",
    )
    parser.add_argument(
        "--video",
        type=Path,
        help="Path to a video file to play instead of a live camera",
    )
    args = parser.parse_args(argv)
    source_provided = args.source is not None
    if args.source is None:
        args.source = [0]
    if args.video:
        if not args.video.exists():
            parser.error(f"Video file not found: {args.video}")
        if source_provided:
            parser.error("--video cannot be combined with --source")
    return args


if __name__ == "__main__":
    run()
