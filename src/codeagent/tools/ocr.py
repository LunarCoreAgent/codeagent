"""OCR tool: extract text from images via tesseract or EasyOCR.

Engine resolution order (``engine="auto"``):
1. pytesseract + tesseract binary (fast, system package)
2. EasyOCR (pure pip install, deep-learning based, no system binary)
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from codeagent.security.policy import RiskLevel
from codeagent.tools.base import Tool

_TESSERACT_HINT = (
    "Install the tesseract binary (e.g. `brew install tesseract` / "
    "`apt install tesseract-ocr`) plus `pip install pytesseract Pillow`, "
    "or use engine='easyocr' (`pip install easyocr`)."
)


class OCRTool(Tool):
    name = "ocr"
    description = (
        "Extract text from an image file (PNG/JPEG/etc.) using OCR. "
        "Supports language selection and engine choice (tesseract/easyocr)."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image file to read text from.",
            },
            "lang": {
                "type": "string",
                "description": (
                    "Language code(s), e.g. 'eng', 'chi_sim', 'eng+chi_sim'. "
                    "Default 'eng'."
                ),
            },
            "engine": {
                "type": "string",
                "enum": ["auto", "tesseract", "easyocr"],
                "description": "OCR engine to use. Default 'auto'.",
            },
        },
        "required": ["image_path"],
    }
    risk_level = RiskLevel.READ_ONLY

    async def execute(
        self,
        image_path: str,
        lang: str = "eng",
        engine: str = "auto",
    ) -> str:
        path = Path(image_path).expanduser()
        if not path.is_file():
            return f"Error: image not found: {path}"

        errors: list[str] = []
        if engine in ("auto", "tesseract"):
            try:
                return self._tesseract(path, lang)
            except RuntimeError as exc:
                errors.append(str(exc))
                if engine == "tesseract":
                    return f"Error: {exc}"
        if engine in ("auto", "easyocr"):
            try:
                return self._easyocr(path, lang)
            except RuntimeError as exc:
                errors.append(str(exc))
                if engine == "easyocr":
                    return f"Error: {exc}"
        return "Error: no OCR engine available. " + " | ".join(errors)

    @staticmethod
    def _tesseract(path: Path, lang: str) -> str:
        if shutil.which("tesseract") is None:
            raise RuntimeError(f"tesseract binary not found. {_TESSERACT_HINT}")
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                f"pytesseract/Pillow not installed. {_TESSERACT_HINT}"
            ) from exc
        text = pytesseract.image_to_string(Image.open(path), lang=lang)
        return text.strip() or "(no text detected)"

    @staticmethod
    def _easyocr(path: Path, lang: str) -> str:
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError(
                "easyocr not installed. `pip install easyocr`."
            ) from exc
        langs = [code.strip() for code in lang.split("+") if code.strip()]
        reader = easyocr.Reader(langs or ["en"], gpu=False)
        results = reader.readtext(str(path), detail=0)
        return "\n".join(results).strip() or "(no text detected)"


def ocr_tools() -> list[Tool]:
    return [OCRTool()]
