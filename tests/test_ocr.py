"""OCR tool: engine resolution and graceful dependency reporting."""

import sys
from pathlib import Path

from codeagent.tools.ocr import OCRTool, ocr_tools


def test_ocr_tool_schema():
    tool = OCRTool()
    assert tool.name == "ocr"
    schema = tool.to_schema()
    assert "image_path" in schema["parameters"]["properties"]
    assert schema["parameters"]["required"] == ["image_path"]


def test_ocr_tools_factory():
    assert len(ocr_tools()) == 1


async def test_ocr_missing_image(tmp_path):
    result = await OCRTool().execute(str(tmp_path / "nope.png"))
    assert "image not found" in result


async def test_ocr_reports_missing_engines(tmp_path, monkeypatch):
    image = tmp_path / "pic.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")  # content irrelevant; engines absent
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    monkeypatch.setitem(sys.modules, "easyocr", None)
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = await OCRTool().execute(str(image))
    assert "no OCR engine available" in result


async def test_ocr_tesseract_engine_path(tmp_path, monkeypatch):
    """When tesseract + pytesseract exist, their output is returned."""
    image = tmp_path / "pic.png"
    image.write_bytes(b"fake")

    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tesseract")

    class FakePytesseract:
        @staticmethod
        def image_to_string(img, lang="eng"):
            return f"text in {lang}"

    class FakeImage:
        @staticmethod
        def open(path):
            return object()

    class FakePIL:
        Image = FakeImage

    monkeypatch.setitem(sys.modules, "pytesseract", FakePytesseract)
    monkeypatch.setitem(sys.modules, "PIL", FakePIL)
    monkeypatch.setitem(sys.modules, "PIL.Image", FakeImage)

    result = await OCRTool().execute(str(image), lang="chi_sim", engine="tesseract")
    assert result == "text in chi_sim"
