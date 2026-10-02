"""Chunk-aware structured extraction and duplicate-aware aggregation."""

from collections.abc import Callable

from app.schemas.intelligence import ExtractionOutput, Sentiment
from app.services.ai_service import OpenAIService
from app.services.grounding import canonical
from app.services.local_extractor import extract_local
from app.services.preprocessing import TextChunk


class Summarizer:
    def __init__(self, provider: str):
        self.provider = provider
        self.ai = OpenAIService() if provider == "openai" else None

    def extract(
        self, chunks: list[TextChunk], metadata: dict, progress: Callable[[str, int], None]
    ) -> ExtractionOutput:
        outputs = []
        for index, chunk in enumerate(chunks):
            if self.ai:
                result = self.ai.extract(chunk.content, chunk.start_line, metadata)
            else:
                result = extract_local(
                    chunk.content,
                    chunk.start_line,
                    metadata.get("participants"),
                    metadata.get("project", ""),
                )
            outputs.append(result)
            progress(
                f"AI analysis · chunk {index + 1} of {len(chunks)}",
                30 + int(25 * (index + 1) / len(chunks)),
            )
        return self.combine(outputs)

    @staticmethod
    def combine(outputs: list[ExtractionOutput]) -> ExtractionOutput:
        combined = {}
        limits = {
            "three_line_summary": 3,
            "executive_summary": 8,
            "detailed_summary": 30,
            "bullet_summary": 20,
            "key_points": 30,
            "decisions": 50,
            "action_items": 80,
            "risks": 50,
            "questions": 40,
            "follow_ups": 30,
            "commitments": 30,
            "dependencies": 30,
            "projects": 30,
            "people": 80,
            "important_dates": 40,
            "topics": 30,
        }
        for field, limit in limits.items():
            unique = []
            seen = set()
            # Round robin represents the whole meeting rather than only the first chunk.
            lists = [getattr(output, field) for output in outputs]
            for offset in range(max((len(items) for items in lists), default=0)):
                for items in lists:
                    if offset < len(items) and canonical(items[offset].text) not in seen:
                        unique.append(items[offset])
                        seen.add(canonical(items[offset].text))
            if (
                field
                not in {
                    "three_line_summary",
                    "executive_summary",
                    "detailed_summary",
                    "bullet_summary",
                    "key_points",
                }
                and len(unique) > limit
            ):
                raise ValueError(
                    f"More than {limit} {field.replace('_', ' ')} were detected. Split this transcript into smaller meetings to avoid silently losing extracted records"
                )
            combined[field] = unique[:limit]
        tones = [
            output.sentiment
            for output in outputs
            if output.sentiment.label != "Not enough evidence"
        ]
        if not tones:
            tone = Sentiment(
                label="Not enough evidence",
                description="No explicit tone signals available; no personality traits are inferred.",
                evidence=[],
            )
        elif len({t.label for t in tones}) == 1:
            tone = tones[0]
        else:
            # Do not invent a synthesis without verifying it in the grounding layer.
            tone = Sentiment(
                label="Mixed",
                description="Both positive and concerned expressions appear in the transcript.",
                evidence=[e for t in tones for e in t.evidence][:5],
            )
        return ExtractionOutput(**combined, sentiment=tone)
