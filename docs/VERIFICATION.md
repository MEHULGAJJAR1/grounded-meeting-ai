# Delivery verification

Validation performed on **2026-10-01**. This report distinguishes actual execution from integrations that need credentials or a container engine.

## Executed successfully

| Area | Evidence/result |
| --- | --- |
| Backend — SQLite | **69 tests passed**, 27.48 s; **90% statement coverage** (2,527 statements). `backend-test-log.txt`, JUnit XML and coverage XML |
| Backend — native PostgreSQL 17 | **69 tests passed**, 28.93 s on disposable UTF-8 databases. `postgres-test-log.txt`, `postgres-test-results.xml` |
| PostgreSQL migration | Initial Alembic migration applied on an actual PostgreSQL database. `postgres-migration-log.txt` |
| Frontend tests | **8 tests passed** (Vitest / Testing Library). `frontend-test-log.txt` |
| Static checks | Python Ruff and frontend ESLint passed; backend/scripts compile successfully. Lint logs included |
| Frontend production build | Vite production build passed. Actual bundled JS/CSS/fonts included under `frontend/web` |
| One-command startup | Ran the exact **`python scripts/run.py`** command through dependency installation, frontend build, migration and Uvicorn startup. Integrated `/login` and `/api/health` returned 200. `launcher-validation-log.txt` |
| Actual browser/application | **11 end-to-end flows passed**, no browser runtime errors or unexpected API errors. `browser-verification.json`, `browser-test-log.txt` |
| Responsive checks | **36 views**: 9 routes at 1440 / 1024 / 768 / 390 px, no page-level horizontal overflow |
| Upload/parsing | Real TXT browser upload/preview/attachment/reanalysis; automated PDF/DOCX/CSV/TXT parser and malformed-file checks |
| Exports | Real PDF, DOCX, JSON, Markdown and CSV downloads in Chromium, plus content/security tests |
| Security/scope | JWT/password/revocation tests; unauthorized meeting/document/action/export/RAG operations; safe-error and validation scenarios |
| Grounding | Missing owner/deadline, ambiguity, nonexistent evidence, unsupported metadata, question resolution, explicit severity and independent verifier association checks |
| SDK contracts | Actual OpenAI SDK structured-output/embedding response parsing with a **test-only intercepted transport**; not production fixture responses and not live OpenAI proof |
| Dependency audit | pip-audit of runtime dependencies and npm audit reported **zero known vulnerabilities** at validation. JSON reports included |
| Docker configuration | Actual Docker Compose v2 `config --quiet` succeeded; db/backend/frontend services resolved. `docker-config-validation.txt` |
| API/schema | **37 REST operations**, 16 ORM tables, OpenAPI schema saved to `openapi.json` |
| Source hygiene | No TODO/FIXME/NotImplementedError implementation markers found; release excludes private `.env`, databases, uploads, tokens, caches and installed dependencies |

The screenshots are captures of the final production build with real local processing and explicitly fictional sample meetings. The sample workspace contains five meetings and 15 extracted action records at capture time; these are not hardcoded dashboard/API totals.

## Browser flows exercised

Registration and empty state; meeting creation and durable background processing; explicit/missing fields; evidence expansion and source navigation; manual action creation, completion, filtering and editing; risk resolution and human question answer; all five export downloads; real document extraction, attachment, stale-result invalidation and reprocessing; scoped retrieval/assistant citations; profile changes; logout/re-login; sample generation and navigation.

These are functional smoke/viewport checks, not a claim of exhaustive device testing or a WCAG certification. Runtime was Python 3.13 / Node 20; source targets Python 3.11+ and CI includes 3.11/3.13. PostgreSQL 17 was validated natively; Compose config targets PostgreSQL 16. No live GitHub Actions run is claimed.

## Explicitly unverified here

- **Live OpenAI calls:** no API credentials were provided. Configure your own `.env` and run `python scripts/live_openai_smoke.py --confirm-live` to perform real, billable extraction/embedding/RAG checks against a disposable fictional dataset.
- **Docker image build/container runtime:** no Docker engine was available. Configuration was validated with the actual CLI, not by pretending containers ran. Reproduce with `python scripts/configure.py` then `docker compose up --build`.
- **Real SMTP delivery:** transport behavior is tested; no external email service credentials were provided.
- **Public deployment/scale:** no multi-replica queue, ANN index, load-test result, distributed quota guarantee, OCR or SSO/MFA deployment is asserted.

The implemented queue is single-worker/single-API-instance with persisted startup recovery. Portable JSON vectors are scanned in process (up to 10,000 owned chunks). Local extraction and lexical embeddings are labelled as such. Support scores are heuristic, not guaranteed hallucination-free probabilities.
