"""Foreground segmentation helpers for ASCII camera frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Protocol

import cv2
import numpy as np


class SegmentationError(RuntimeError):
    """Raised when the foreground segmenter cannot be configured or run."""


@dataclass(slots=True)
class SegmentationConfig:
    """Configuration bundle for :class:`ForegroundSegmenter`."""

    backend: str = "mog2"
    history: int = 200
    var_threshold: float = 25.0
    detect_shadows: bool = False
    kernel_size: int = 5
    min_confidence: float = 0.3


class _SegmentationBackend(Protocol):
    def process(self, frame: np.ndarray) -> np.ndarray:
        ...

    def close(self) -> None:
        ...


class _Mog2Backend:
    def __init__(self, config: SegmentationConfig) -> None:
        kernel = max(1, config.kernel_size)
        if kernel % 2 == 0:
            kernel += 1
        self._kernel = (
            np.ones((kernel, kernel), dtype=np.uint8) if kernel > 1 else None
        )
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=max(2, config.history),
            varThreshold=max(1.0, float(config.var_threshold)),
            detectShadows=bool(config.detect_shadows),
        )

    def process(self, frame: np.ndarray) -> np.ndarray:
        mask = self._subtractor.apply(frame)
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        if self._kernel is not None:
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel, iterations=1)
        return mask > 0

    def close(self) -> None:  # pragma: no cover - nothing to release
        pass


class _SelfieBackend:
    def __init__(self, config: SegmentationConfig) -> None:
        try:
            from mediapipe.python.solutions import selfie_segmentation
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SegmentationError(
                "Selfie backend requires mediapipe. Install ascii-cam[ml] to enable it."
            ) from exc

        self._segmenter = selfie_segmentation.SelfieSegmentation(model_selection=1)
        self._min_confidence = float(config.min_confidence)

    def process(self, frame: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._segmenter.process(rgb)
        mask = getattr(result, "segmentation_mask", None)
        if mask is None:
            return np.zeros(frame.shape[:2], dtype=bool)
        return (mask.astype(np.float32) >= self._min_confidence)

    def close(self) -> None:  # pragma: no cover - destructor path
        self._segmenter.close()


class ForegroundSegmenter:
    """High-level interface for foreground segmentation backends."""

    _BACKENDS: ClassVar[tuple[str, ...]] = ("mog2", "selfie")

    def __init__(self, config: SegmentationConfig | None = None) -> None:
        self.config = config or SegmentationConfig()
        backend = self.config.backend
        if backend not in self._BACKENDS:
            raise SegmentationError(
                f"Unsupported backend '{backend}'. Supported: {', '.join(self._BACKENDS)}"
            )
        self._backend_name = backend
        self._backend = self._create_backend(self.config)

    @classmethod
    def available_backends(cls) -> tuple[str, ...]:
        return cls._BACKENDS

    @property
    def backend(self) -> str:
        return self._backend_name

    def compute_mask(self, frame: np.ndarray) -> np.ndarray:
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise SegmentationError("Segmentation expects BGR frames")
        mask = self._backend.process(frame)
        if mask.shape != frame.shape[:2]:
            raise SegmentationError("Backend returned mask with unexpected shape")
        return mask.astype(bool)

    def switch_backend(self, backend: str) -> None:
        if backend == self._backend_name:
            return
        if backend not in self._BACKENDS:
            raise SegmentationError(
                f"Unsupported backend '{backend}'. Supported: {', '.join(self._BACKENDS)}"
            )
        self._backend.close()
        self.config = SegmentationConfig(
            backend=backend,
            history=self.config.history,
            var_threshold=self.config.var_threshold,
            detect_shadows=self.config.detect_shadows,
            kernel_size=self.config.kernel_size,
            min_confidence=self.config.min_confidence,
        )
        self._backend = self._create_backend(self.config)
        self._backend_name = backend

    def close(self) -> None:
        self._backend.close()

    def __del__(self) -> None:  # pragma: no cover - destructor best effort
        try:
            self.close()
        except Exception:
            pass

    def _create_backend(self, config: SegmentationConfig) -> _SegmentationBackend:
        if config.backend == "mog2":
            return _Mog2Backend(config)
        if config.backend == "selfie":
            return _SelfieBackend(config)
        raise SegmentationError(
            f"Unsupported backend '{config.backend}'. Supported: {', '.join(self._BACKENDS)}"
        )
