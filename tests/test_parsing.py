import pytest
from fpdf import FPDF

from app.services.parsing import (
    EmptyFileError,
    UnsupportedFileTypeError,
    parse_bytes,
)


def _make_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=14)
    pdf.cell(text=text, w=0, h=10)
    return bytes(pdf.output())


def test_parse_txt_utf8():
    assert parse_bytes("你好，FastAPI".encode(), ".txt") == "你好，FastAPI"


def test_parse_md():
    text = parse_bytes("# 标题\n\n正文".encode(), ".md")
    assert "标题" in text


def test_parse_gb18030_fallback():
    data = "中文编码兼容测试".encode("gb18030")
    assert parse_bytes(data, ".txt") == "中文编码兼容测试"


def test_unsupported_extension():
    with pytest.raises(UnsupportedFileTypeError):
        parse_bytes(b"whatever", ".docx")


def test_empty_bytes():
    with pytest.raises(EmptyFileError):
        parse_bytes(b"", ".txt")


def test_whitespace_only_text_file():
    with pytest.raises(EmptyFileError):
        parse_bytes(b"   \n\n  ", ".txt")


def test_parse_pdf():
    data = _make_pdf("FastAPI knowledge base test document")
    text = parse_bytes(data, ".pdf")
    assert "FastAPI" in text
    assert "knowledge base" in text


def test_corrupt_pdf_raises():
    with pytest.raises(ValueError):
        parse_bytes(b"this is definitely not a pdf", ".pdf")
