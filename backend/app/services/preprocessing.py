"""Line-preserving cleanup, explicit speaker analysis and citation-aware chunks."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

CONTROL_LABELS = {
    "action",
    "action item",
    "action items",
    "decisions",
    "risks",
    "blockers",
    "questions",
    "participants",
    "attendees",
    "agenda",
    "notes",
    "next steps",
    "dependencies",
    "commitments",
    "meeting date",
    "date",
    "owner",
    "decision",
    "tentative decision",
    "rejected proposal",
    "risk",
    "blocker",
    "question",
    "open question",
    "unanswered",
    "answer",
    "topic",
    "project",
    "note",
    "summary",
    "dependency",
    "follow-up",
    "follow up",
    "commitment",
    "document",
    "page",
    "due",
    "priority",
    "status",
}
SPEAKER = re.compile(
    r"^(?:\[(?:\d{1,2}:\d{2}(?::\d{2})?|CSV row \d+)\]\s*)?([\w][\w .'-]{0,79}):\s*(.*)$"
)


def preprocess(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def speaker_line(line: str) -> tuple[str | None, str]:
    match = SPEAKER.match(line)
    if (
        match
        and match.group(1).casefold() not in CONTROL_LABELS
        and not re.fullmatch(r"row \d+", match.group(1), re.I)
    ):
        return match.group(1).strip(), match.group(2).strip()
    return None, line


def speaker_statistics(text: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    current = None
    for number, line in enumerate(text.splitlines(), 1):
        name, content = speaker_line(line)
        if line.startswith("[Document:"):
            current = None
            continue
        if name:
            current = name
            result.setdefault(name, {"word_count": 0, "lines": []})
        if current and content:
            result[current]["word_count"] += len(re.findall(r"\b\w+\b", content))
            result[current]["lines"].append(number)
    total = sum(item["word_count"] for item in result.values())
    for item in result.values():
        item["speaking_share"] = round(item["word_count"] / total, 4) if total else 0.0
    return result


@dataclass(frozen=True)
class TextChunk:
    content: str
    start_line: int
    end_line: int
    content_hash: str
    document_id: str | None = None
    page_number: int | None = None


def chunk_transcript(text: str, documents: list | None = None) -> list[TextChunk]:
    """Do not let a vector chunk cross an uploaded page/document boundary."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=6000,
        chunk_overlap=600,
        separators=["\n\n", "\n", ". ", " ", ""],
        strip_whitespace=False,
    )
    headers = list(re.finditer(r"^\[Document: (.*?) \| (page|section) (\d+)\]", text, re.M))
    boundaries = sorted({0, len(text), *(match.start() for match in headers)})
    chunks: list[TextChunk] = []
    for segment_start, segment_end in zip(boundaries, boundaries[1:]):
        segment = text[segment_start:segment_end]
        if not segment.strip():
            continue
        marker = next((header for header in headers if header.start() == segment_start), None)
        page = int(marker.group(3)) if marker and marker.group(2) == "page" else None
        document_id = next(
            (d.id for d in documents or [] if marker and d.filename == marker.group(1)), None
        )
        cursor = 0
        for part in splitter.split_text(segment):
            position = segment.find(part, max(0, cursor - 700))
            if position < 0:
                position = segment.find(part)
            if position < 0:
                raise ValueError("Unable to locate transcript chunk in original text")
            offset = segment_start + position
            start_line = text.count("\n", 0, offset) + 1
            end_line = text.count("\n", 0, offset + len(part)) + 1
            chunks.append(
                TextChunk(
                    part,
                    start_line,
                    end_line,
                    hashlib.sha256(part.encode()).hexdigest(),
                    document_id,
                    page,
                )
            )
            cursor = position + len(part)
    return chunks
