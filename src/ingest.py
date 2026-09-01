"""Parse user-uploaded documents into searchable chunks."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.retrieve import DocumentChunk, split_markdown_text


MAX_FILE_BYTES = 10 * 1024 * 1024
SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf"}
MIN_EXTRACTED_PAGE_CHARS = 20
MAX_OCR_PAGES = 20
OCR_RENDER_SCALE = 2.0


class IngestionError(ValueError):
    """A safe, user-facing error raised when a document cannot be parsed."""


def decode_text(data: bytes) -> str:
    """Decode common Chinese and UTF text encodings."""

    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise IngestionError("文本编码无法识别，请将文件另存为 UTF-8 后重试。")


def split_plain_text(
    text: str,
    source: str,
    heading: str,
    max_chars: int = 1000,
    overlap_chars: int = 150,
) -> list[DocumentChunk]:
    """Split long plain text while keeping source and section metadata."""

    cleaned = text.strip()
    if not cleaned:
        return []
    if max_chars <= 0 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("切分参数无效。")

    chunks: list[DocumentChunk] = []
    start = 0
    part = 1
    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))
        if end < len(cleaned):
            boundary = max(
                cleaned.rfind("\n", start, end),
                cleaned.rfind("。", start, end),
                cleaned.rfind("！", start, end),
                cleaned.rfind("？", start, end),
            )
            if boundary > start + max_chars // 2:
                end = boundary + 1

        content = cleaned[start:end].strip()
        if content:
            part_heading = heading if len(cleaned) <= max_chars else f"{heading} · 片段 {part}"
            chunks.append(
                DocumentChunk(
                    source=source,
                    heading=part_heading,
                    content=content,
                )
            )
            part += 1

        if end >= len(cleaned):
            break
        start = end - overlap_chars

    return chunks


def _ocr_lines(result: Any) -> str:
    """Normalize RapidOCR output into one readable text block."""

    lines: list[str] = []
    for item in result or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = str(item[1]).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def ocr_pdf_pages(
    data: bytes,
    page_indices: list[int],
    *,
    engine: Any | None = None,
) -> dict[int, str]:
    """Render selected PDF pages and recognize text locally with RapidOCR."""

    if not page_indices:
        return {}
    if len(page_indices) > MAX_OCR_PAGES:
        raise IngestionError(
            f"扫描页超过 {MAX_OCR_PAGES} 页，请拆分 PDF 后重新上传。"
        )
    try:
        import pymupdf
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR

        ocr_engine = engine or RapidOCR()
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise IngestionError("OCR 组件初始化失败，请检查部署依赖。") from exc

    recognized: dict[int, str] = {}
    try:
        for page_index in page_indices:
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                pixmap.height, pixmap.width, pixmap.n
            )
            raw_result, _ = ocr_engine(image)
            recognized[page_index] = _ocr_lines(raw_result)
    except Exception as exc:
        raise IngestionError("扫描版 PDF 的 OCR 识别失败。") from exc
    finally:
        document.close()
    return recognized


def parse_pdf(
    name: str,
    data: bytes,
    *,
    ocr_engine: Any | None = None,
) -> list[DocumentChunk]:
    """Extract text from normal PDFs and OCR pages without a text layer."""

    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise IngestionError("PDF 文件无法读取，可能已损坏或不是有效 PDF。") from exc

    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception as exc:
            raise IngestionError("PDF 已加密，请先解除密码保护。") from exc
        if not unlocked:
            raise IngestionError("PDF 已加密，请先解除密码保护。")

    extracted_pages: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        extracted_pages.append(page_text.strip())

    scan_indices = [
        index
        for index, text in enumerate(extracted_pages)
        if len("".join(text.split())) < MIN_EXTRACTED_PAGE_CHARS
    ]
    ocr_pages = ocr_pdf_pages(data, scan_indices, engine=ocr_engine)

    chunks: list[DocumentChunk] = []
    for page_index, extracted_text in enumerate(extracted_pages):
        ocr_text = ocr_pages.get(page_index, "").strip()
        page_text = ocr_text or extracted_text
        heading = f"第 {page_index + 1} 页"
        if ocr_text:
            heading += " · OCR"
        chunks.extend(
            split_plain_text(
                page_text,
                source=name,
                heading=heading,
            )
        )

    if not chunks:
        raise IngestionError(
            "PDF 中没有识别到文字。请检查扫描清晰度、方向或页面内容。"
        )
    return chunks


def parse_document(name: str, data: bytes) -> list[DocumentChunk]:
    """Parse one supported upload without saving it to disk."""

    safe_name = Path(name).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IngestionError("仅支持 Markdown、TXT 和 PDF 文件。")
    if not data:
        raise IngestionError("文件内容为空。")
    if len(data) > MAX_FILE_BYTES:
        raise IngestionError("单个文件不能超过 10MB。")

    if suffix == ".pdf":
        return parse_pdf(safe_name, data)

    text = decode_text(data)
    if suffix == ".md":
        chunks = split_markdown_text(text, safe_name)
    else:
        chunks = split_plain_text(text, safe_name, "TXT 文档")

    if not chunks:
        raise IngestionError("文件中没有可检索的文字。")
    return chunks
