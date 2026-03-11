"""Curses-based full screen UI for the ASCII camera."""

from __future__ import annotations

import curses
import time
from dataclasses import dataclass
from typing import Any, Optional

from .ascii_renderer import AsciiFrame, CHAR_ASPECT_RATIO, frame_to_ascii
from .camera import CameraConfig, CameraError, CameraStream
from .glitch import GlitchEngine
from .segmentation import ForegroundSegmenter, SegmentationConfig, SegmentationError

STATUS_BAR_HEIGHT = 1
MIN_WIDTH = 40
MIN_HEIGHT = 12
BRIGHTNESS_STEPS: tuple[int, ...] = (25, 50, 75, 100)

SourceInput = int | str


@dataclass
class UIOptions:
    refresh_delay: float = 0.03  # Seconds between frames (~33 fps)
    start_segmentation: bool = True
    segmentation_backend: str = "mog2"
    camera_sources: tuple[SourceInput, ...] = (0,)
    start_source_index: int = 0
    start_glitch: bool = True


def _create_segmenter(backend: str) -> tuple[Optional[ForegroundSegmenter], Optional[str]]:
    try:
        return ForegroundSegmenter(SegmentationConfig(backend=backend)), None
    except SegmentationError as err:
        return None, f"Segmentation unavailable: {err}"


def _open_camera_source(source: SourceInput) -> tuple[Optional[CameraStream], Optional[str]]:
    camera = CameraStream(CameraConfig(source=source))
    try:
        camera.open()
    except CameraError as err:
        descriptor = "video file" if isinstance(source, str) else "camera source"
        return None, f"Failed to open {descriptor} {source}: {err}"
    return camera, None


def _change_camera_source(
    current_camera: Optional[CameraStream],
    source: SourceInput,
) -> tuple[Optional[CameraStream], Optional[str]]:
    new_camera, error = _open_camera_source(source)
    if error:
        return current_camera, error
    if current_camera:
        current_camera.close()
    return new_camera, None


def run_ui(stdscr: Any, options: Optional[UIOptions] = None) -> None:
    opts = options or UIOptions()
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    green_attr = _init_green_pair()
    glitch_engine = GlitchEngine()

    message: Optional[str] = None
    ascii_frame: Optional[AsciiFrame] = None
    segmenter: Optional[ForegroundSegmenter] = None
    segmentation_enabled = opts.start_segmentation
    brightness_index = len(BRIGHTNESS_STEPS) - 1
    available_backends = ForegroundSegmenter.available_backends()
    backend = (
        opts.segmentation_backend
        if opts.segmentation_backend in available_backends
        else available_backends[0]
    )
    glitch_enabled = opts.start_glitch
    glitch_engine.set_enabled(glitch_enabled)

    if segmentation_enabled:
        segmenter, init_error = _create_segmenter(backend)
        if init_error:
            message = init_error
            segmentation_enabled = False

    sources: list[SourceInput] = list(opts.camera_sources)
    if not sources:
        sources = [0]
    source_index = min(max(opts.start_source_index, 0), len(sources) - 1)
    camera: Optional[CameraStream] = None

    try:
        while True:
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                break

            if key in (ord("f"), ord("F")):
                segmentation_enabled = not segmentation_enabled
                if segmentation_enabled:
                    if not segmenter:
                        segmenter, init_error = _create_segmenter(backend)
                        if init_error:
                            message = init_error
                            segmentation_enabled = False
                        else:
                            message = f"Foreground mask on ({backend})"
                    else:
                        message = f"Foreground mask on ({backend})"
                else:
                    message = "Foreground mask off"
                continue

            if key in (ord("b"), ord("B")):
                brightness_index = (brightness_index + 1) % len(BRIGHTNESS_STEPS)
                message = f"Brightness {BRIGHTNESS_STEPS[brightness_index]}%"
                continue

            if key in (ord("g"), ord("G")):
                glitch_enabled = not glitch_enabled
                glitch_engine.set_enabled(glitch_enabled)
                message = f"Glitch {'on' if glitch_enabled else 'off'}"
                continue

            height, width = stdscr.getmaxyx()
            usable_height = height - STATUS_BAR_HEIGHT

            if width < MIN_WIDTH or usable_height < MIN_HEIGHT:
                _draw_too_small(
                    stdscr,
                    width,
                    height,
                    backend,
                    BRIGHTNESS_STEPS[brightness_index],
                    _format_source_label(sources[source_index]),
                    glitch_enabled,
                )
                stdscr.refresh()
                time.sleep(opts.refresh_delay)
                continue

            if camera is None:
                camera, cam_error = _change_camera_source(None, sources[source_index])
                if cam_error:
                    message = cam_error
                    stdscr.erase()
                    _draw_status_bar(
                        stdscr,
                        width,
                        height,
                        message,
                        segmentation_enabled,
                        backend,
                        None,
                        BRIGHTNESS_STEPS[brightness_index],
                        _format_source_label(sources[source_index]),
                        glitch_enabled,
                    )
                    stdscr.refresh()
                    time.sleep(opts.refresh_delay)
                    continue

            try:
                assert camera is not None
                frame = camera.read_frame()
                mask = segmenter.compute_mask(frame) if (segmenter and segmentation_enabled) else None
                render_height = max(1, int(usable_height / CHAR_ASPECT_RATIO))
                ascii_frame = frame_to_ascii(
                    frame,
                    width,
                    render_height,
                    foreground_mask=mask,
                    brightness=BRIGHTNESS_STEPS[brightness_index] / 100.0,
                )
                message = None
            except CameraError as err:
                message = str(err)
                if camera:
                    camera.close()
                camera = None
                ascii_frame = None
            except SegmentationError as err:
                message = f"Segmentation error: {err}"[: width - 1]
                ascii_frame = None
                segmentation_enabled = False

            display_frame = glitch_engine.apply(ascii_frame)
            stdscr.erase()
            _render_ascii(stdscr, display_frame, width, green_attr)
            _draw_status_bar(
                stdscr,
                width,
                height,
                message,
                segmentation_enabled,
                backend,
                display_frame.foreground_ratio if display_frame else None,
                BRIGHTNESS_STEPS[brightness_index],
                _format_source_label(sources[source_index]),
                glitch_enabled,
            )
            stdscr.refresh()
            time.sleep(opts.refresh_delay)
    finally:
        if camera:
            camera.close()
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
    brightness_percent: int,
    source_label: str,
    glitch_enabled: bool,
) -> None:
    status_text = message or _status_hint()
    ratio = "--" if foreground_ratio is None else f"{foreground_ratio * 100:.0f}%"
    seg_info = "off" if not segmentation_enabled else f"{backend}:{ratio}"
    bright_info = f"br:{brightness_percent}%"
    glitch_info = "gl:on" if glitch_enabled else "gl:off"
    info = (
        f" | {width}x{height} | src {source_label} | fg {seg_info} | {bright_info} | {glitch_info}"
    )
    full_status = (status_text + info)[: max(0, width - 1)]
    status_line = full_status.ljust(width - 1)
    try:
        stdscr.addstr(height - 1, 0, status_line, curses.A_REVERSE)
    except curses.error:
        pass


def _status_hint() -> str:
    hints = ["q:quit", "f:mask", "b:bright", "g:glitch"]
    return " ".join(hints)


def _format_source_label(source: SourceInput) -> str:
    return source if isinstance(source, str) else str(source)


def _draw_too_small(
    stdscr: Any,
    width: int,
    height: int,
    backend: str,
    brightness_percent: int,
    source_label: str,
    glitch_enabled: bool,
) -> None:
    stdscr.erase()
    msg = "Increase terminal size to display ASCII camera"
    y = max(0, height // 2)
    x = max(0, (width - len(msg)) // 2)
    try:
        stdscr.addstr(y, x, msg)
    except curses.error:
        pass
    _draw_status_bar(
        stdscr,
        width,
        height,
        "Window too small",
        False,
        backend,
        None,
        brightness_percent,
        source_label,
        glitch_enabled,
    )


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
