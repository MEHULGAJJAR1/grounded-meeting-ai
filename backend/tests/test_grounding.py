import pytest
from pydantic import ValidationError

from app.schemas.intelligence import (
    Claim,
    Evidence,
    Verification,
    VerificationBatch,
)
from app.services.grounding import explicit_calendar_date, locate_evidence, verify_extraction
from app.services.local_extractor import extract_local
from app.services.preprocessing import chunk_transcript, preprocess, speaker_statistics


def analyze(text):
    return verify_extraction(extract_local(text), text)


def test_normal_transcript_source_locations():
    text = "Maya: Action: Rahul to send the report by 2026-10-08.\nRahul: Decision: We agreed to use staged deployment."
    result, report = analyze(text)
    assert result["action_items"][0]["owner"] == "Rahul"
    assert result["action_items"][0]["due_date"] == "2026-10-08"
    assert result["action_items"][0]["evidence"][0]["line_start"] == 1
    assert report["flagged"] == 0


def test_transcript_without_owner():
    result, _ = analyze("Maya: Action: update the deployment runbook by 2026-10-08.")
    assert result["action_items"][0]["owner"] == "Unassigned"
    assert result["action_items"][0]["due_date"] == "2026-10-08"


def test_transcript_without_deadline():
    result, _ = analyze("Rahul: I'll update the deployment runbook.")
    assert result["action_items"][0]["owner"] == "Rahul"
    assert result["action_items"][0]["due_date"] == "Not specified"
    assert result["action_items"][0]["priority_provenance"] == "application_default"


def test_ambiguous_action_is_not_silently_confirmed():
    result, report = analyze("Maya: We should update the deployment runbook.")
    item = result["action_items"][0]
    assert item["owner"] == "Unassigned"
    assert item["grounding_status"] == "review" and item["confidence"] <= 0.6
    assert report["review"] > 0


def test_empty_extraction_is_valid_but_does_not_invent_content():
    extraction = extract_local("")
    assert extraction.action_items == [] and extraction.executive_summary == []
    result, report = verify_extraction(extraction, "")
    assert result["sentiment"]["label"] == "Not enough evidence" and report["checked_claims"] == 0


def test_missing_quote_is_flagged_and_withheld():
    text = "Maya: Action: update the deployment runbook."
    extraction = extract_local(text)
    extraction.action_items[0].evidence[0].quote = "Rahul approved a Friday release."
    result, report = verify_extraction(extraction, text)
    assert result["action_items"] == []
    assert report["flagged"] > 0 and report["flagged_claims"]
    assert report["flagged_claims"][0]["confidence"] == 0


def test_hallucinated_metadata_resets_sentinels():
    text = "Maya: Action: update the deployment runbook."
    extraction = extract_local(text)
    action = extraction.action_items[0]
    action.owner = "Rahul"
    action.owner_evidence = text
    action.due_date = "2026-10-08"
    action.due_date_evidence = text
    result, report = verify_extraction(extraction, text)
    item = result["action_items"][0]
    assert item["owner"] == "Unassigned" and item["due_date"] == "Not specified"
    assert item["confidence"] <= 0.55 and item["grounding_status"] == "review"
    assert report["metadata_corrections"] == 2


def test_mentioning_person_does_not_assign_owner():
    text = "Maya: Action: update the deployment runbook. Rahul attended the call."
    extraction = extract_local(text)
    extraction.action_items[0].owner = "Rahul"
    extraction.action_items[0].owner_evidence = text
    result, _ = verify_extraction(extraction, text)
    assert result["action_items"][0]["owner"] == "Unassigned"


def test_relative_deadline_is_preserved_not_invented():
    result, _ = analyze("Rahul: I'll publish the deployment checklist by next Friday.")
    assert result["action_items"][0]["due_date"].casefold() == "next friday"
    assert explicit_calendar_date("next Friday") is None
    assert explicit_calendar_date("October 7") is None
    assert explicit_calendar_date("2026-02-30") is None
    assert explicit_calendar_date("October 7, 2026").isoformat() == "2026-10-07"


def test_reported_line_numbers_are_recomputed():
    text = "Maya: Action: update the deployment runbook."
    extraction = extract_local(text)
    extraction.action_items[0].evidence[0].line_start = 99
    result, _ = verify_extraction(extraction, text)
    assert result["action_items"][0]["evidence"][0]["line_start"] == 1
    assert locate_evidence("update   the deployment", text)["quote"] == "update the deployment"


def test_structured_schema_rejects_bad_confidence_and_extras():
    value = {
        "text": "A source fact",
        "evidence": [{"quote": "A source fact", "line_start": 1, "line_end": 1}],
        "confidence": 2,
    }
    with pytest.raises(ValidationError):
        Claim.model_validate(value)
    value["confidence"] = float("nan")
    with pytest.raises(ValidationError):
        Claim.model_validate(value)
    value["confidence"] = 0.8
    value["made_up_field"] = True
    with pytest.raises(ValidationError):
        Claim.model_validate(value)
    with pytest.raises(ValidationError):
        Evidence(quote="", line_start=0, line_end=1)


def test_valid_quote_does_not_prove_false_paraphrase(monkeypatch):
    text = "Maya: Proposal: We might deploy on Friday."
    extraction = extract_local(text)
    extraction.executive_summary[0].text = "The production release was approved for Friday."

    def independent_checks(self, claims, context):
        return VerificationBatch(
            checks=[
                Verification(
                    claim_id=c["claim_id"],
                    verdict="unsupported" if "approved" in c["claim"]["text"] else "supported",
                    reason="Proposal is not a confirmed decision",
                    score=0.05 if "approved" in c["claim"]["text"] else 0.9,
                )
                for c in claims
            ]
        )

    from app.config import get_settings

    settings = get_settings()
    old = settings.openai_api_key
    settings.openai_api_key = "contract-test-not-a-real-key"
    monkeypatch.setattr("app.services.ai_service.OpenAIService.verify", independent_checks)
    try:
        result, report = verify_extraction(extraction, text, "openai")
        assert all("approved" not in c["text"] for c in result["executive_summary"])
        assert report["flagged"] > 0
    finally:
        settings.openai_api_key = old


def test_chunking_offsets_and_speaker_metrics():
    text = preprocess(
        "Maya: Hello  team.\r\nRahul: Two words.\r\n" + "Maya: deployment discussion.\n" * 600
    )
    chunks = chunk_transcript(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.content in text and chunk.start_line <= chunk.end_line
    stats = speaker_statistics("Maya: one two three\nRahul: one")
    assert stats["Maya"]["speaking_share"] == 0.75
    assert speaker_statistics("No speaker labels in this text") == {}


def test_decisions_not_extracted_as_tasks():
    result, _ = analyze(
        "Maya: Decision: We agreed to perform the migration in a maintenance window."
    )
    assert len(result["decisions"]) == 1 and result["action_items"] == []


def test_page_aware_chunks_do_not_mix_document_citations():
    text = "[Document: report.pdf | page 1]\nMaya: First page discussion.\n\n[Document: report.pdf | page 2]\nRahul: Second page action."
    chunks = chunk_transcript(text)
    assert len(chunks) == 2
    assert chunks[0].page_number == 1 and chunks[1].page_number == 2
    assert "Second page" not in chunks[0].content


def test_question_with_later_answer_is_not_verified_unanswered():
    text = (
        "Maya: Open question: Who approves deployment?\n"
        + "Maya: Discussion continues.\n" * 12
        + "Rahul: Answer: Maya approves deployment."
    )
    result, report = analyze(text)
    assert result["questions"][0]["grounding_status"] == "review"
    assert report["review"] > 0


def test_questions_do_not_become_unassigned_action_records():
    result, _ = analyze("Rahul: Open question: Who will approve the release?")
    assert result["action_items"] == [] and result["questions"]


def test_risk_severity_is_not_invented_from_words_like_delay():
    result, _ = analyze("Maya: Risk: capacity approval may delay delivery.")
    assert result["risks"][0]["severity"] == "Unknown"
    result, _ = analyze("Maya: Risk: High severity. Capacity approval may delay delivery.")
    assert result["risks"][0]["severity"] == "High"


def test_unsupported_nondefault_priority_without_quote_is_flagged():
    text = "Maya: Action: write the runbook."
    extracted = extract_local(text)
    extracted.action_items[0].priority = "Critical"
    result, report = verify_extraction(extracted, text)
    assert result["action_items"][0]["priority"] == "Medium"
    assert result["action_items"][0]["grounding_status"] == "review"
    assert result["action_items"][0]["confidence"] <= 0.55
    assert report["metadata_corrections"] == 1
