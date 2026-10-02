"""Actual text extraction; image-only PDFs are rejected rather than fabricated."""

import csv
from io import BytesIO, StringIO
from pathlib import Path
import zipfile

from docx import Document as WordDocument
from pypdf import PdfReader

from app.config import get_settings

ALLOWED_TYPES = {"txt", "pdf", "docx", "csv"}


class DocumentParseError(ValueError):
    pass


def validate_file(filename: str, data: bytes) -> str:
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED_TYPES:
        raise DocumentParseError("Supported files are TXT, PDF, DOCX and CSV")
    if not data:
        raise DocumentParseError("The uploaded file is empty")
    if extension == "pdf" and not data.startswith(b"%PDF-"):
        raise DocumentParseError("This file is not a valid PDF")
    if extension == "docx":
        if not data.startswith(b"PK"):
            raise DocumentParseError("This file is not a valid DOCX")
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise DocumentParseError("The file is not a Word OOXML document")
                if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
                    raise DocumentParseError("Expanded document exceeds the safety limit")
                if any(item.flag_bits & 1 for item in archive.infolist()):
                    raise DocumentParseError("Encrypted DOCX files are not supported")
        except zipfile.BadZipFile:
            raise DocumentParseError("Corrupt DOCX archive") from None
    return extension


def extract_document(filename: str, data: bytes) -> tuple[str, list[dict]]:
    kind = validate_file(filename, data)
    pages: list[dict] = []
    try:
        if kind == "pdf":
            reader = PdfReader(BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise DocumentParseError("Encrypted PDFs are not supported")
            if len(reader.pages) > 300:
                raise DocumentParseError("PDF exceeds the 300-page limit")
            for number, page in enumerate(reader.pages, 1):
                pages.append({"page": number, "text": (page.extract_text() or "").strip()})
                if sum(len(p["text"]) for p in pages) > get_settings().max_transcript_chars:
                    raise DocumentParseError("Extracted text exceeds MAX_TRANSCRIPT_CHARS")
        elif kind == "docx":
            word = WordDocument(BytesIO(data))
            # iter_inner_content preserves paragraph/table ordering in the document.
            segments = []
            for block in word.iter_inner_content():
                if hasattr(block, "text"):
                    if block.text.strip():
                        segments.append(block.text.strip())
                else:
                    segments.extend(
                        " | ".join(cell.text.strip() for cell in row.cells) for row in block.rows
                    )
            pages = [{"page": None, "section": 1, "text": "\n".join(segments)}]
        elif kind == "csv":
            decoded = data.decode("utf-8-sig")
            rows = list(csv.reader(StringIO(decoded)))
            if len(rows) > 20000:
                raise DocumentParseError("CSV exceeds the 20,000-row limit")
            columns = [cell.strip().casefold() for cell in rows[0]] if rows else []
            text_column = next(
                (
                    columns.index(name)
                    for name in ("text", "content", "utterance", "transcript")
                    if name in columns
                ),
                None,
            )
            speaker_column = columns.index("speaker") if "speaker" in columns else None
            segments = []
            for number, row in enumerate(rows, 1):
                if (
                    number > 1
                    and text_column is not None
                    and speaker_column is not None
                    and len(row) > max(text_column, speaker_column)
                ):
                    speaker, utterance = row[speaker_column].strip(), row[text_column].strip()
                    if speaker:
                        segments.append(f"[CSV row {number}] {speaker}: {utterance}")
                    else:
                        segments.append(f"[CSV row {number}] {utterance}")
                    other = [
                        f"{columns[i] if i < len(columns) else 'column'}={cell.strip()}"
                        for i, cell in enumerate(row)
                        if i not in {speaker_column, text_column} and cell.strip()
                    ]
                    if other:
                        segments.append("[CSV metadata] " + " | ".join(other))
                elif number > 1 and len(row) == len(columns):
                    segments.append(
                        f"[CSV row {number}] "
                        + " | ".join(
                            f"{header}: {cell.strip()}" for header, cell in zip(columns, row)
                        )
                    )
                else:
                    segments.append(
                        f"[CSV row {number}] " + " | ".join(cell.strip() for cell in row)
                    )
            pages = [{"page": None, "section": 1, "text": "\n".join(segments)}]
        else:
            decoded = data.decode("utf-8-sig")
            if "\x00" in decoded:
                raise DocumentParseError("Binary data is not a text transcript")
            pages = [{"page": None, "section": 1, "text": decoded.strip()}]
    except DocumentParseError:
        raise
    except UnicodeDecodeError:
        raise DocumentParseError("Text and CSV files must use UTF-8 encoding") from None
    except Exception:
        raise DocumentParseError(
            "Could not read this document; it may be corrupt or unsupported"
        ) from None
    text = "\n\n".join(p["text"] for p in pages if p["text"])
    if not text.strip():
        raise DocumentParseError(
            "No selectable text found. OCR/image-only PDFs are not supported; upload a text transcript"
        )
    if len(text) > get_settings().max_transcript_chars:
        raise DocumentParseError("Extracted text exceeds MAX_TRANSCRIPT_CHARS")
    return text, pages


def attachment_text(document) -> str:
    segments = []
    for page in document.pages:
        if not page["text"].strip():
            continue
        reference = (
            f"page {page['page']}" if page.get("page") else f"section {page.get('section', 1)}"
        )
        segments.append(f"[Document: {document.filename} | {reference}]\n{page['text']}")
    return "\n\n".join(segments)
