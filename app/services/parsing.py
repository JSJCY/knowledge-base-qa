"""把上传文件解析为纯文本。支持 .txt / .md / .pdf。"""

import io

from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


class UnsupportedFileTypeError(ValueError):
    def __init__(self, extension: str) -> None:
        super().__init__(f"不支持的文件类型：{extension or '(无扩展名)'}，仅支持 .txt / .md / .pdf")
        self.extension = extension


class EmptyFileError(ValueError):
    pass


def parse_bytes(data: bytes, extension: str) -> str:
    """按扩展名解析文件字节为文本，失败时抛出 ValueError 子类。"""
    ext = extension.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(ext)
    if not data:
        raise EmptyFileError("文件内容为空")
    if ext == ".pdf":
        return _parse_pdf(data)
    text = _decode_text(data)
    if not text.strip():
        raise EmptyFileError("文件没有可提取的文本")
    return text


def _decode_text(data: bytes) -> str:
    """UTF-8 优先，失败回退 GB18030（兼容 GBK/GB2312 中文文件）。"""
    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise ValueError(f"PDF 解析失败：{exc}") from exc
    text = "\n\n".join(p.strip() for p in pages if p.strip())
    if not text.strip():
        raise EmptyFileError("PDF 中未提取到文本（可能是扫描版）")
    return text
