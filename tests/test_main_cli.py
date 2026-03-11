"""CLI argument parsing tests for the curses UI entry point."""

from pathlib import Path

import pytest

from matrix_cam.main import _parse_args


def test_parse_args_defaults() -> None:
    args = _parse_args([])
    assert args.refresh_delay == 0.03
    assert args.source == [0]
    assert args.segment_backend == "mog2"
    assert args.no_mask is False
    assert args.video is None


def test_parse_args_multiple_sources() -> None:
    args = _parse_args(["--source", "0", "2", "5"])
    assert args.source == [0, 2, 5]


def test_parse_args_accepts_video_file(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"")
    args = _parse_args(["--video", str(video_path)])
    assert args.video == video_path
    assert args.source == [0]


def test_parse_args_rejects_video_with_sources(tmp_path: Path) -> None:
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"")
    with pytest.raises(SystemExit):
        _parse_args(["--source", "0", "--video", str(video_path)])
