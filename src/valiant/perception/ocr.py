"""Optional ear-tag OCR adapter.

Given a BGR crop and a :class:`~valiant.perception.types.Detection`, fill
``.text`` when an OCR backend is available and ``enabled=True``. Never hard-
requires OCR packages: missing deps or runtime failures leave text empty
(soft degrade). Library code must not call SystemExit.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from valiant.core.errors import Degradable
from valiant.perception.types import Detection

# Soft-degrade latch for the process (one-shot print via Degradable).
_ocr_state = Degradable()


def ocr_available() -> bool:
    """True if at least one optional OCR backend can be imported."""
    try:
        import pytesseract  # noqa: F401

        return True
    except ImportError:
        pass
    try:
        import easyocr  # noqa: F401

        return True
    except ImportError:
        return False


def _decode_with_pytesseract(crop_bgr: Any) -> str:
    import pytesseract

    try:
        import cv2

        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    except Exception:
        gray = crop_bgr
    raw = pytesseract.image_to_string(gray, config="--psm 8")
    return "".join(ch for ch in raw.strip().upper() if ch.isalnum())[:8]


def _decode_with_easyocr(crop_bgr: Any) -> str:
    import easyocr

    reader = easyocr.Reader(["en"], verbose=False)
    results = reader.readtext(crop_bgr)
    if not results:
        return ""
    # EasyOCR returns (bbox, text, confidence); take highest-confidence hit.
    best = max(results, key=lambda r: float(r[2]) if len(r) > 2 else 0.0)
    raw = str(best[1]) if len(best) > 1 else ""
    return "".join(ch for ch in raw.strip().upper() if ch.isalnum())[:8]


def read_tag_text(
    crop_bgr: Any,
    detection: Detection,
    *,
    enabled: bool = False,
) -> Detection:
    """Return a Detection with ``.text`` filled when OCR succeeds.

    When ``enabled`` is False, or no backend is installed, or OCR raises,
    returns a Detection with empty ``text`` (original detection otherwise
    preserved). Latches a soft-degraded reason on first backend failure.
    """
    if not enabled or crop_bgr is None:
        return replace(detection, text="")

    text = ""
    try:
        try:
            import pytesseract  # noqa: F401

            text = _decode_with_pytesseract(crop_bgr)
        except ImportError:
            try:
                import easyocr  # noqa: F401

                text = _decode_with_easyocr(crop_bgr)
            except ImportError:
                _ocr_state.latch_degraded("OCR backend missing (pytesseract/easyocr)")
                return replace(detection, text="")
    except Exception as exc:
        _ocr_state.latch_degraded(f"OCR failed: {exc}")
        return replace(detection, text="")

    return replace(detection, text=text)


def ocr_degraded() -> str | None:
    """Reason OCR latched degraded, or None if still healthy / unused."""
    return _ocr_state.degraded
