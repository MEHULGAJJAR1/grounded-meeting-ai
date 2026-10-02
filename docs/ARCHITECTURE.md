# Architecture and design decisions

## Boundaries

The application separates HTTP routing, request/AI schemas, domain persistence and services. Routers authenticate first and resolve owned resources through shared access helpers. The React client uses a same-origin Axios API client, protected routes, cancellable resource hooks and reusable evidence/action/grounding/progress components. Page components orchestrate operations; large intelligence/chart presentations live in their own modules. CSS is organised by feature.

## Persistence and ownership

SQLAlchemy 2 models use UUID identifiers, foreign keys, ownership indexes and cascades. User owns meetings/documents/actions/notifications/audit rows. Meeting links its transcript, participants, validated summary/report, decisions, actions, risks, questions, topics, documents and chunks. Each chunk has one embedding metadata record. Revoked tokens support explicit logout; token-version changes invalidate sessions after a password change. SQLite foreign keys are enabled. PostgreSQL uses the same model/migration architecture with psycopg and UTF-8 databases.

Source input and the cleaned working copy are separate. Saved summaries are validated intelligence objects; grounding reports preserve supported/uncertain/withheld entries and field-level corrections. An action's `source_snapshot` retains the original validated extraction. Current human-edited records are marked user-provided, with confidence zero rather than reusing an AI score as proof of human changes. Original scores/evidence remain available through the snapshot.

## Processing lifecycle

`draft → queued → processing → completed`, or `failed` with a safe, actionable error. Submission is persisted before returning 202. The background worker reads the durable queue; startup recovers interrupted processing. Reported progress comes from real phases and completed chunks/verifier batches, not elapsed-time animation. Stages cover preprocessing, source-aware chunking, embedding generation, extraction, aggregation, independent verification and atomic persistence. Failed provider/validation operations do not save partial outputs.

Extraction collections have explicit bounds. Summary views intentionally have presentation limits. Exceeding a non-summary collection limit fails with split-transcript guidance rather than truncating actions, questions or decisions. The final post-verification object is validated with Pydantic again before saving.

**Concurrency contract:** one API process/worker. In-process recovery/locking is not multi-replica safe. Do not run several Uvicorn workers or independent replicas against this queue. A distributed deployment requires an external transactional queue/lease mechanism. Notifications and request limits are also process-local.

## Two AI modes

OpenAI mode uses the actual SDK and Pydantic Structured Outputs for extraction and RAG. A separate verification request checks entailment, including task-to-owner/deadline/priority/status association and explicit risk severity. Verifier batches receive full-meeting context, since later answers or corrections can change an interpretation. Evidence locations are computed by the server, not trusted from model-generated line numbers.

Local mode is a conservative English literal/pattern baseline, not a generative LLM. It uses actual source excerpts, explicit assignment/deadline cues and stable 384-dimensional lexical hashing. It is useful without credentials but cannot prove paraphrased entailment or fully interpret arbitrary discourse. Both UI and API identify the mode. No production service returns test fixtures or fake OpenAI vectors.

In either mode, a quote match alone is not a proof of meaning or real-world truth. Unknown owners/deadlines use `Unassigned`/`Not specified`; defaults are not evidence-backed assertions. Relative deadlines are preserved without calendar inference. Risk severity stays Unknown without explicit evidence. Unsupported core claims are withheld; uncertain candidates remain visibly review-labelled. Support scores are heuristics, not calibrated probabilities.

## Document provenance

Original files are private, size/type checked and stored with metadata, extracted text/sections and extraction errors. PDF text retains physical page numbers; chunks do not cross source page/document boundaries. TXT, CSV and DOCX use synthetic sections, never inferred physical DOCX pages. Common CSV speaker/text columns retain genuine speaker labels; row labels are not treated as names. Scanned/encrypted PDFs are handled with explicit errors/guidance, not invented text. A deleted file does not automatically delete its already-imported transcript copy; the UI warns about that retention behavior.

## Retrieval and assistant

Every retrieval query is restricted by current user ownership and, when supplied, an owned meeting ID. Chunk vectors keep provider/model/dimension identity. Queries use the corresponding embedding model; OpenAI and lexical indexes are not mixed as if equivalent. Cosine similarity and lexical overlap provide ranking, not a confidence probability.

Explicit assignment/deadline/status queries consult current mutable records. Latest-meeting queries select real owned records, and next-week calendar queries use the next Monday–Sunday in the user's timezone. Unverified current-record candidates are excluded from assistant assertions. Narrative queries retrieve source passages. OpenAI answer proposals must cite returned source IDs, include matching quote strings and pass an independent entailment check. Unsupported/unknown citations are withheld; insufficient-support declarations do not produce asserted claims. Local answers are clearly described as source excerpts. Current human-entered record statements are labelled as such.

Assistant history is browser-memory only; no conversation table or cross-account memory exists. It is sent only as bounded user/assistant messages, never arbitrary system-role input.

## Exports and notifications

One presenter supplies consistent representations to APIs and export services. JSON preserves complete validated intelligence, grounding and action provenance. Markdown, PDF and DOCX include evidence; CSV provides editable action rows and formula-prefix protection. PDF and XML text are escaped. PDF fonts are bundled with their license.

Notifications persist in the database and appear in-app. The worker checks upcoming/overdue calendar deadlines periodically (five minutes) and emits processing-completion notifications. Transport implementations support inbox-only or optional SMTP with environment credentials and TLS. SMTP failures are safely logged and never falsely reported as email sent.

## Operational limits and scale path

- Default 10 MiB upload, 150,000-character meeting limit, 300 PDF pages, 20,000 CSV rows and bounded DOCX decompression.
- One API/processing worker; no distributed queue or shared quota enforcement.
- Portable JSON vector storage and a maximum 10,000-owned-chunk in-process retrieval scan. Not an ANN/vector-database deployment.
- Eight descriptive dashboard metrics and six real record-derived charts; no model-generated productivity/quality scores.
- No OCR/audio transcription, organisational sharing, multi-assignee identity directory, persistent conversations or live calendar integrations.
- Public hosting requires HTTPS, trusted proxy configuration, encrypted private storage/backups, verified email/onboarding policy and appropriate monitoring.

For scale, preserve the current ownership predicates and verification contracts while moving jobs to an external durable queue, vectors to tenant-filtered pgvector/ANN storage, quotas to a shared store and parsing to isolated workers. These are explicit evolution paths, not claims about features already deployed.
