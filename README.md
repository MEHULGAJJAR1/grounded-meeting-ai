# Grounded AI Meeting Notes Summariser & Action Tracker

**A complete, source-backed meeting intelligence workspace — not a mock dashboard.**

Grounded turns pasted transcripts and uploaded documents into traceable summaries, decisions, manageable action items, risks and questions. Every accepted AI claim carries evidence; an independent verification stage checks the proposal before it is saved. A React workspace connects to real FastAPI endpoints, a persistent database, document parsers, export services and a user-scoped retrieval engine.

![Grounded dashboard](docs/screenshots/dashboard.png)

## Run locally with one command

**Prerequisites:** Python **3.11–3.13**, Node.js **20+** with npm, and internet access for the first dependency installation. Use a terminal in this extracted repository:

```bash
python scripts/run.py
```

Open **http://localhost:8000**. The launcher creates an isolated `.venv`, generates private secrets in `.env`, installs dependencies, builds React, applies database migrations and starts the integrated application. No account, password or API key is hardcoded. Register your own account, or choose **Explore sample workspace** on the login page in development.

After installation, `python scripts/run.py --skip-install` starts the existing environment and build. `--port 8010` overrides the port. Stop with **Ctrl+C**. On Windows, `py -3.11 scripts/run.py` is an equivalent launcher when Python is installed through the Python Launcher.

### Real OpenAI or an honest offline baseline

The default `AI_PROVIDER=auto` uses OpenAI when `OPENAI_API_KEY` is configured. Without a key, it uses a **labelled, deterministic local extractive engine** and **384-dimensional lexical feature embeddings**. These operate on actual source text; they are neither mocked API responses nor a learned semantic model. Local mode is useful for offline operation, testing, sample data and conservative English-language transcript extraction. It is not equivalent to LLM synthesis.

For full AI functionality, put your own key in the generated `.env`, choose a model supporting OpenAI Structured Outputs, and restart:

```dotenv
AI_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Set `OPENAI_API_KEY` in that same private file. Do not commit it. `AI_PROVIDER=openai` fails configuration when the key is missing; provider failures do **not** silently substitute fabricated output. OpenAI mode makes real SDK requests for structured extraction, separate entailment verification, embeddings and cited RAG answers. Configured OpenAI requests send relevant transcript/question/source content to OpenAI and incur charges on your account. Changing models/providers requires reanalysing meetings to rebuild their indexes.

**Validation boundary:** local end-to-end operation, provider wire contracts, SQLite and native PostgreSQL have been tested. Live OpenAI calls and live SMTP delivery were not exercised in the delivery environment. Docker Compose configuration was validated, but a Docker engine was unavailable for container build/runtime verification. See [the verification report](docs/VERIFICATION.md) rather than treating these external integrations as already live-tested.

## Features

### Meeting intelligence

- Three-line, executive, detailed and bullet summaries; fewer lines when the source has fewer facts.
- Key points, **Confirmed / Tentative / Rejected** decisions and proposals.
- Actions with task, owner, literal/calendar deadline, priority, status, dependencies, quotes and a 0–1 support score.
- Risks, blockers, dependencies, delivery/technical/resource concerns, unanswered questions, follow-ups and commitments.
- Explicitly mentioned projects, people, dates and topics; a descriptive tone overview only when evidence exists.
- Label-derived speaker word counts, word-share percentages, topics and assigned-task counts. No personality, demographic or sensitive-trait inference; unavailable speaker statistics remain unavailable.
- Descriptive meeting-health counts, never an invented “meeting quality” score.
- Collapsible detail sections, source navigation, original input, numbered cleaned source lines and a visible grounding report.

### Real action tracking

- Persistent action CRUD, owner assignment, due-date changes, notes, dependencies and completion/reopening.
- **All, Pending, Completed, Overdue, High Priority, Unassigned and My Tasks** filters, plus search and sorting.
- Extracted actions are saved as actual records, not just summary bullets.
- Human edits become explicitly user-provided states. The original validated extraction, evidence and score are retained separately; they do not become proof of a new human-entered owner or deadline.
- Editing source text invalidates stale summaries/indexes while retaining human-managed actions. Reanalysis does not overwrite human changes.
- “My Tasks” matches the signed-in user's display name to the recorded owner; it does not guess an identity from an ambiguous name.

### Workspace, documents and retrieval

- Login, registration, protected routes, JWT expiry/revocation, password changes and logout.
- Dashboard with **eight real metrics and six charts**: action status, priority, meetings over time, owners, decisions over time and risks over time.
- Meetings list/grid, creation/editing, processing detail, action tracker, document library, search, assistant and settings pages.
- TXT, selectable-text PDF, DOCX and CSV parsing with original downloads, extracted text, status and persisted extraction errors.
- Real PDF page citations; non-paginated formats use sections rather than invented physical page numbers. CSV `speaker` plus `text`/`content`/`utterance`/`transcript` columns preserve speaker labels; other CSVs retain readable header/cell data.
- User-owned chunks and embedding metadata. OpenAI cosine similarity plus lexical overlap provides hybrid semantic retrieval; local mode reports its lexical method honestly.
- Assignment/deadline/status queries use current records rather than stale summary states. “Next week” uses the next Monday–Sunday in the user's timezone. Answer claims need valid source IDs, matching quotes and, in OpenAI mode, a separate entailment check. Unverified current-record candidates are excluded from assistant assertions.
- Assistant history is intentionally browser-memory only, clears on new conversation/navigation reload and is never shared between accounts.
- **PDF, DOCX, JSON, Markdown and action CSV** exports with evidence/provenance. CSV formula injection is mitigated; PDF/XML content is escaped.
- In-app processing-complete and upcoming/overdue notifications, read state and optional SMTP through a transport interface.
- Accessible labelled controls, keyboard-focus modal handling, empty/loading/error states, real server-stage polling, actual upload-byte progress and toasts.

## Grounding rules and limits

1. Whitespace/Unicode-normalise a working copy; preserve raw input separately.
2. Split source text with **LangChain's `RecursiveCharacterTextSplitter`**, preserving line offsets and document/page boundaries.
3. Generate embeddings and strictly validate structured extraction with Pydantic v2.
4. Locate every evidence quote against real source text. Only case/whitespace normalization is permitted, never fuzzy quote replacement.
5. Verify core claims independently. OpenAI batches receive full-meeting context to expose later answers or corrections.
6. Independently verify task owner/deadline/priority/status association. An unsupported owner does not erase a supported task: it becomes exactly **`Unassigned`**; a missing/unsupported deadline becomes exactly **`Not specified`**. Unsupported non-default metadata is reported and reduces support.
7. `Medium` priority and `Pending` status are labelled **application defaults** when not explicitly stated. Risk severity stays **`Unknown`** without explicit evidence. Relative/ambiguous deadlines remain literal; no year or calendar date is guessed.
8. Withhold unsupported core claims, keep uncertain candidates clearly labelled for review, validate the final intelligence object again and persist all outputs atomically.

A support score describes this checking process; it is **not a calibrated probability, proof of real-world truth, or a guarantee against every model error**. Read the original quotes, especially for ambiguity or high-stakes use. Grounding report core-claim counts and metadata corrections are separate measures. Dashboard counts include clearly labelled review candidates.

The default transcript limit is 150,000 characters; uploads are 10 MiB. Per-collection extraction limits are enforced. Excess non-summary records fail explicitly with split-transcript guidance, rather than silently losing actions or decisions. Scanned PDFs need external OCR; encrypted PDFs must be unlocked. DOCX page layout is not inferred. See [architecture and operational limits](docs/ARCHITECTURE.md).

## Technology stack

**Python · FastAPI · Pydantic v2 · SQLAlchemy · SQLite / PostgreSQL · Alembic · Uvicorn · python-dotenv · JWT (PyJWT) · bcrypt · OpenAI API / Structured Outputs · LangChain · React · Vite · Axios · React Router · Recharts · Lucide**

Document/export tooling: `pypdf`, `python-docx`, `reportlab`, Python CSV; database driver: `psycopg`; quality tooling: Pytest, pytest-cov, Vitest, Testing Library and opt-in Playwright/Chromium checks. Frontend fonts and icon assets are bundled, not fetched from a CDN at runtime.

## Architecture

```mermaid
flowchart TD
    Browser[React workspace] -->|same-origin /api + bearer JWT| API[FastAPI routes]
    API --> Auth[Authorization + user scope]
    Auth --> DB[(SQLAlchemy: SQLite / PostgreSQL)]
    API --> Queue[Durable queued meeting state]
    Queue --> Worker[Single background worker + startup recovery]
    Worker --> Parse[Normalize and LangChain page-aware chunks]
    Parse --> Extract[OpenAI structured extraction or labelled local extraction]
    Extract --> Verify[Quote checks + independent entailment / metadata verification]
    Verify --> Final[Pydantic final validation + atomic save]
    Final --> DB
    Parse --> Embed[OpenAI or labelled local embeddings]
    Embed --> DB
    Auth --> RAG[User-scoped hybrid retrieval + current records]
    DB --> RAG
    RAG --> Answer[Answer quote and entailment verification]
    Answer --> Browser
    DB --> Export[PDF / DOCX / JSON / Markdown / CSV]
    DB --> Notify[In-app notifications + optional SMTP]
```

The worker is durable through persisted queue state and startup recovery, but is deliberately **single-worker / single-API-instance**. It is not a multi-replica distributed queue. JSON vector storage keeps SQLite and PostgreSQL portable; retrieval ranks at most 10,000 owned chunks per query. For larger deployments, introduce a durable external queue, shared rate limits and a pgvector/ANN index while retaining tenant predicates.

### Repository layout

```text
backend/
  app/
    models/         ORM entities, relationships and cascade rules
    schemas/        request and structured AI/final-output contracts
    routers/        auth, meetings, actions, documents, dashboard, RAG, exports
    services/       parsing, extraction, verification, processing, retrieval, exports
    utils/          authorization, JWT/bcrypt, logging and limits
    assets/         licensed PDF fonts
    main.py         lifecycle, migrations, worker, errors and SPA serving
  alembic/          versioned database migrations
  tests/            isolated backend/contract/security tests
frontend/
  src/
    components/     accessible UI, action/grounding/progress/source/chart panels
    pages/          connected application routes
    context/        auth and toast state
    hooks/          cancellable API resources
    services/       relative Axios client and shared formatting
    styles/         modular responsive CSS
  public/           application favicon
  package-lock.json
scripts/             configuration, one-command launcher and smoke checks
docs/                architecture, API, security, verification and actual screenshots
Dockerfile            frontend-build, backend and nginx frontend targets
docker-compose.yml    PostgreSQL + API + frontend with persistent volumes
.env.example          environment template; never real credentials
requirements.txt      pinned runtime Python dependencies
requirements-dev.txt  development/test/lint dependencies
```

## Environment configuration

`python scripts/configure.py` creates `.env` if needed and generates strong JWT/PostgreSQL secrets. It never prints secret values or overwrites configured nonempty secrets. The launcher runs it automatically. Environment variables override dotenv values.

| Setting | Purpose |
| --- | --- |
| `APP_ENV` | `development`, `production` or `test` |
| `APP_HOST`, `APP_PORT` | Local server binding/port |
| `OPENAI_API_KEY` | Private backend-only API key |
| `AI_PROVIDER` | `auto`, `openai` or `local` |
| `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL` | Compatible model names |
| `OPENAI_TIMEOUT_SECONDS` | Provider timeout; bounded retries are implemented |
| `DATABASE_URL` | SQLite URL or `postgresql+psycopg://` URL |
| `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Signing secret and token lifetime |
| `UPLOAD_DIR`, `MAX_UPLOAD_SIZE`, `MAX_TRANSCRIPT_CHARS` | Private storage/processing limits |
| `CORS_ORIGINS` | Explicit comma-separated allowed origins |
| `ALLOW_DEMO_DATA` | Development-only sample workspace/data |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` | Optional email transport |
| `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD` | Compose database configuration |

Production refuses a short signing key, wildcard CORS or enabled development demos. Set `APP_ENV=production`, `ALLOW_DEMO_DATA=false`, an appropriate database URL and explicit HTTPS origins. Terminate HTTPS at a trusted reverse proxy. Keep `.env`, databases and uploaded files private and backed up; encrypt storage/backup media for confidential meetings. The default SQLite file is `data/grounded.db`; uploads are under `uploads/`. Neither is shipped in the ZIP.

### Database and migrations

Startup automatically runs Alembic upgrades. For explicit migration administration after installing dependencies:

```bash
python -m alembic -c backend/alembic.ini upgrade head
```

Models include **User, Meeting, Participant, Transcript, MeetingSummary, Decision, ActionItem, Risk, Question, Topic, Document, DocumentChunk, EmbeddingMetadata and AuditLog**, plus Notification and RevokedToken. There is an initial migration, foreign keys, ownership indexes and cascade behavior. Use UTF-8 PostgreSQL databases. Changing `DATABASE_URL` selects a different database; it does not transfer existing SQLite data.

### Docker

Install Docker Engine/Desktop with Compose v2. In this repository:

```bash
python scripts/configure.py
docker compose up --build
```

Frontend: **http://localhost:8080** · integrated API/SPA: **http://localhost:8000** · API docs: **http://localhost:8000/api/docs**. PostgreSQL 16 is internal to the Compose network. Database/uploads use named volumes, migrations run on startup, the API runs as a non-root user and health checks gate startup. The frontend proxies `/api` to the backend, so the browser never calls a container's localhost. Demo endpoints are disabled in production Compose; register an account and create actual meetings.

`docker compose down` stops services without deleting data. **`docker compose down -v` destroys the named database/upload volumes.**

## Development and testing

For hot reload after initial provisioning, use two terminals:

```bash
# Terminal 1 (use .venv/bin/python on POSIX; .venv\Scripts\python.exe on Windows)
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload --no-access-log

# Terminal 2
cd frontend
npm run dev
```

Run the Python terminal with the provisioned virtual environment activated. Vite serves on port 5173 with a same-origin `/api` proxy. Package locks and pinned Python versions make installs repeatable.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -c backend/pytest.ini backend/tests --cov=backend/app --cov-report=term-missing
python -m ruff check backend scripts
cd frontend
npm ci
npm test
npm run build
```

Backend fixtures isolate SQLite by default; do **not** point `TEST_DATABASE_URL` at a real application's database — the tests recreate tables. PostgreSQL testing:

```bash
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DISPOSABLE_TEST_DB python -m pytest -c backend/pytest.ini backend/tests
```

The GitHub Actions workflow checks SQLite on supported Python versions, PostgreSQL with migrations, frontend tests/build and Compose configuration. Test-only SDK transports exercise actual OpenAI SDK structured-output contracts without spending API credits; there are no production fixture-returning AI functions.

Real-browser smoke checks use actual API/database operations, not network mocks:

```bash
python -m pip install playwright
python -m playwright install chromium
python scripts/browser_smoke.py --url http://localhost:8000
```

Linux browser hosts may need `python -m playwright install --with-deps chromium`. The script covers auth, processing, evidence navigation, action/risk/question changes, documents, five downloads, retrieval, settings, logout/relogin and responsive views. It writes a JSON report and screenshots. Run it in development/local mode, with demo data enabled and a disposable workspace. For explicitly consented live provider checks after configuring your key: `python scripts/live_openai_smoke.py --confirm-live`.

## API and sample data

Interactive OpenAPI: **`/api/docs`** · machine-readable schema: **`/api/openapi.json`**. See [the API guide](docs/API.md) for route groups, payloads and error shapes. Protected routes require `Authorization: Bearer` with the issued access token; resources outside the current account return 404. Processing submission returns 202 and status is available through polling.

The development **Load sample meetings** control creates five fictional meetings with participants, confirmed/tentative/rejected decisions, assigned/unassigned tasks, calendar/literal/missing deadlines, risks, questions and source TXT files. They are processed with the actual local engine and remain isolated to that account. Loading is idempotent per sample meeting title. The login-page sample session generates a new private account, not shared hardcoded credentials.

## Screenshots

Actual Chromium captures of the running application are included, not design placeholders:

- [Login](docs/screenshots/login.png)
- [Dashboard](docs/screenshots/dashboard.png) · [Mobile dashboard](docs/screenshots/dashboard-mobile.png)
- [Meeting detail](docs/screenshots/meeting-detail.png)
- [Action tracker](docs/screenshots/actions.png)
- [Document library](docs/screenshots/documents.png)
- [AI assistant](docs/screenshots/assistant.png)
- [Smart search](docs/screenshots/search.png)
- [Settings](docs/screenshots/settings.png)

## Future improvements

Scale the existing design with an external job queue/shared rate limiter and pgvector/ANN search; add OCR, calendar integrations, opt-in email verification/MFA, organisation roles, multi-assignee identities and explicitly consented persistent conversations. These are outside the delivered scope, not unfinished application pages.

## Resume-ready project explanation

> Built Grounded, a full-stack meeting intelligence application that converts transcripts and documents into evidence-linked summaries and persistent action records. Implemented strict structured extraction, independent source/entailment checks and user-scoped retrieval, with a React action-management workspace, SQLAlchemy persistence, document exports and automated validation.

### Three ATS-friendly resume bullets

- **Developed a full-stack AI meeting intelligence SaaS using Python, FastAPI, Pydantic v2, SQLAlchemy, PostgreSQL/SQLite and React**, delivering JWT-authenticated meeting processing, persistent action CRUD, document uploads and an eight-metric/six-chart dashboard.
- **Integrated OpenAI Structured Outputs, LangChain text splitting and embedding-based RAG**, implementing independent quote/entailment verification, explicit missing-field fallbacks, source citations and tenant-scoped retrieval to reduce unsupported assertions.
- **Engineered automated Pytest/Vitest and Chromium workflow checks, Alembic migrations, Docker Compose deployment and PDF/DOCX/JSON/Markdown/CSV exports**, preserving human-edit provenance and environment-only credentials.

### Interview talking points

- **Why two AI stages?** Extraction is only a proposal. Evidence matching is deterministic; a separate verifier checks meaning and task-to-owner/deadline association. Matching quotes alone cannot validate an invented interpretation.
- **Why direct OpenAI SDK plus LangChain?** The SDK supplies strict structured contracts; LangChain supplies proven source-aware splitting. A lightweight scoped retrieval service keeps security predicates and current-record precedence explicit rather than hiding them in an agent chain.
- **How is multi-user isolation enforced?** Resolve the authenticated user first, scope every meeting/document/action/index query, check ownership before modifications and reject unknown RAG citation IDs. Database/authorization tests cover horizontal access attempts.
- **How do you preserve user edits?** Keep original validated snapshots separately, mark mutable values as user-provided, retain managed actions when source changes and prevent reanalysis from overwriting them.
- **What would you change for scale?** Replace the single recovered worker and in-process vector scan with a distributed durable queue and tenant-filtered ANN index, without claiming the current deployment already has those guarantees.

## License

Project code is MIT licensed. Bundled fonts have their own licenses in `backend/app/assets/` and `licenses/`; see [third-party notices](THIRD_PARTY_NOTICES.md). Keep all applicable notices when redistributing.
