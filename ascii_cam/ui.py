"""Curses-based full screen UI for the ASCII camera."""

from __future__ import annotations

import curses
import time
from dataclasses import dataclass
from typing import Any, Optional

from .ascii_renderer import AsciiFrame, CHAR_ASPECT_RATIO, frame_to_ascii
from .camera import CameraError, CameraStream
from .segmentation import ForegroundSegmenter, SegmentationConfig, SegmentationError

STATUS_BAR_HEIGHT = 1
MIN_WIDTH = 40
MIN_HEIGHT = 12


@dataclass
class UIOptions:
    refresh_delay: float = 0.03  # Seconds between frames (~33 fps)
    start_segmentation: bool = False
    segmentation_backend: str = "mog2"


def _create_segmenter(backend: str) -> tuple[Optional[ForegroundSegmenter], Optional[str]]:
    try:
        return ForegroundSegmenter(SegmentationConfig(backend=backend)), None
    except SegmentationError as err:
        return None, f"Segmentation unavailable: {err}"


def run_ui(stdscr: Any, options: Optional[UIOptions] = None) -> None:
    opts = options or UIOptions()
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    green_attr = _init_green_pair()

    message: Optional[str] = None
    ascii_frame: Optional[AsciiFrame] = None
    segmenter: Optional[ForegroundSegmenter] = None
    segmentation_enabled = opts.start_segmentation
    backends = ForegroundSegmenter.available_backends()
    try:
        backend_index = backends.index(opts.segmentation_backend)
    except ValueError:
        backend_index = 0

    if segmentation_enabled:
        segmenter, init_error = _create_segmenter(backends[backend_index])
        if init_error:
            message = init_error
            segmentation_enabled = False

    with CameraStream() as camera:
        while True:
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                break

            if key in (ord("f"), ord("F")):
                segmentation_enabled = not segmentation_enabled
                if segmentation_enabled:
                    if not segmenter:
                        segmenter, init_error = _create_segmenter(backends[backend_index])
                        if init_error:
                            message = init_error
                            segmentation_enabled = False
                        else:
                            message = f"Foreground mask on ({backends[backend_index]})"
                    else:
                        message = "Foreground mask on"
                else:
                    message = "Foreground mask off"
                continue

            if key in (ord("b"), ord("B")):
                backend_index = (backend_index + 1) % len(backends)
                target_backend = backends[backend_index]
                if segmentation_enabled:
                    if segmenter:
                        segmenter.close()
                    segmenter, init_error = _create_segmenter(target_backend)
                    if init_error:
                        message = init_error
                        backend_index = (backend_index - 1) % len(backends)
                    else:
                        message = f"Using {target_backend} backend"
                else:
                    message = f"Selected {target_backend} backend"
                continue

            height, width = stdscr.getmaxyx()
            usable_height = height - STATUS_BAR_HEIGHT

            if width < MIN_WIDTH or usable_height < MIN_HEIGHT:
                _draw_too_small(stdscr, width, height)
                stdscr.refresh()
                time.sleep(opts.refresh_delay)
                continue

            try:
                frame = camera.read_frame()
                mask = segmenter.compute_mask(frame) if (segmenter and segmentation_enabled) else None
                render_height = max(1, int(usable_height / CHAR_ASPECT_RATIO))
                ascii_frame = frame_to_ascii(
                    frame,
                    width,
                    render_height,
                    foreground_mask=mask,
                )
                message = None
            except CameraError as err:
                message = str(err)
                ascii_frame = None
            except SegmentationError as err:
                message = f"Segmentation error: {err}"[: width - 1]
                ascii_frame = None
                segmentation_enabled = False

            stdscr.erase()
            _render_ascii(stdscr, ascii_frame, width, green_attr)
            _draw_status_bar(
                stdscr,
                width,
                height,
                message,
                segmentation_enabled,
                backends[backend_index],
                ascii_frame.foreground_ratio if ascii_frame else None,
            )
            stdscr.refresh()
            time.sleep(opts.refresh_delay)

    if segmenter:
        segmenter.close()


def _render_ascii(
    stdscr: Any,
    ascii_frame: Optional[AsciiFrame],
    width: int,
    attr: int,
) -> None:
    if not ascii_frame:
        return

    for row_idx, row in enumerate(ascii_frame.rows):
        if row_idx >= stdscr.getmaxyx()[0] - STATUS_BAR_HEIGHT:
            break
        try:
            stdscr.addstr(row_idx, 0, row[:width], attr)
        except curses.error:
            continue


def _draw_status_bar(
    stdscr: Any,
    width: int,
    height: int,
    message: Optional[str],
    segmentation_enabled: bool,
    backend: str,
    foreground_ratio: Optional[float],
) -> None:
    status_text = message or "q:quit f:mask b:backend"
    ratio = "--" if foreground_ratio is None else f"{foreground_ratio * 100:.0f}%"
    seg_info = "off" if not segmentation_enabled else f"{backend}:{ratio}"
    info = f" | {width}x{height} | fg {seg_info}"
    full_status = (status_text + info)[: max(0, width - 1)]
    status_line = full_status.ljust(width - 1)
    try:
        stdscr.addstr(height - 1, 0, status_line, curses.A_REVERSE)
    except curses.error:
        pass


def _draw_too_small(stdscr: Any, width: int, height: int) -> None:
    stdscr.erase()
    msg = "Increase terminal size to display ASCII camera"
    y = max(0, height // 2)
    x = max(0, (width - len(msg)) // 2)
    try:
        stdscr.addstr(y, x, msg)
    except curses.error:
        pass
    _draw_status_bar(stdscr, width, height, "Window too small", False, "mog2", None)


def _init_green_pair() -> int:
    if not curses.has_colors():
        return curses.A_NORMAL

    curses.start_color()
    try:
        curses.use_default_colors()
        background = -1
    except curses.error:
        background = curses.COLOR_BLACK

    try:
        curses.init_pair(1, curses.COLOR_GREEN, background)
        return curses.color_pair(1) | curses.A_BOLD
    except curses.error:
        return curses.A_NORMAL
