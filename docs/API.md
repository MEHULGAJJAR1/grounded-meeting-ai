# API guide

Base path: `/api`. Interactive documentation: `/api/docs`; schema: `/api/openapi.json`.

All data routes require the JWT issued by registration/login in an `Authorization: Bearer` header. Health/config and authentication endpoints are public. Development bootstrap routes are disabled outside development or when `ALLOW_DEMO_DATA=false`.

## Route groups

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/register` | Create account and issue session |
| POST | `/auth/login` | Authenticate email/password |
| GET / PUT | `/auth/me` | Read/edit own profile and preferences |
| POST | `/auth/change-password` | Change password and invalidate sessions |
| POST | `/auth/logout` | Revoke current token |
| GET / POST | `/meetings` | Paginated owned meeting list / creation |
| GET / PUT / DELETE | `/meetings/{id}` | Owned detail / editing / cascade deletion |
| POST | `/meetings/{id}/process` | Persist processing job; returns 202 |
| GET | `/meetings/{id}/processing-status` | Real status, stage, progress and safe error |
| GET | `/meetings/{id}/export/{format}` | PDF, DOCX, JSON, Markdown or action CSV |
| GET / POST | `/action-items` | Owned filters/search/sorting / manual creation |
| PUT / DELETE | `/action-items/{id}` | Human action changes / deletion |
| PUT | `/risks/{id}` | Human Open/Resolved workflow state |
| PUT | `/questions/{id}` | Human answer / unanswered workflow state |
| GET | `/documents` | Paginated owned upload metadata |
| POST | `/documents/upload` | Multipart extraction, optional owned meeting link |
| GET / DELETE | `/documents/{id}` | Extracted content / delete private file |
| GET | `/documents/{id}/download` | Authenticated original download |
| POST | `/documents/{id}/attach` | Append actual extracted text to owned meeting |
| POST | `/search` | Scoped hybrid retrieval with sources |
| POST | `/ask` | Grounded answer claims and citations |
| GET | `/dashboard/stats` | Actual owned record counts/deadline/recent items |
| GET | `/dashboard/charts` | Status, priority, owner and six-month aggregate data |
| GET | `/notifications` | In-app notifications and unread count |
| PUT | `/notifications/{id}/read` | Mark own notification read |
| GET | `/audit-log` | Own recent metadata-only audit history |
| POST | `/dev/demo-session` | New isolated fictional development workspace |
| POST | `/dev/demo-data` | Idempotent samples in current development account |
| GET | `/health` | Service/database availability |
| GET | `/auth/configuration` | Safe public capabilities; never credential values |

## Payloads

Register with `name`, `email`, `password`; login with `email`, `password`. These endpoints accept JSON, not OAuth form bodies. Registration returns `access_token`, `token_type` and the profile. Never save returned tokens to a tracked file.

A meeting creation example (replace values with your own source data):

```json
{
  "title": "Platform sprint",
  "date": "2026-10-01",
  "meeting_type": "Sprint planning",
  "project": "Atlas",
  "participants": ["Maya", "Rahul"],
  "transcript": "Maya: Action: Rahul to write the release runbook by 2026-10-08.\nRahul: Open question: Who approves deployment?"
}
```

Take the returned `id`, call its processing endpoint, poll status until completed/failed, then fetch detail. No fixed demo IDs are part of the API. Detail includes raw/cleaned source, validated summaries, grounding report, action records, decisions, risks, questions, participants, topics, documents and descriptive health counts.

Each AI action in the validated intelligence payload contains `text`, `owner`, literal `due_date`, priority/status, evidence, confidence and grounding/provenance fields. **Editable REST action records** instead use a nullable ISO calendar `due_date` plus `due_date_text` so a literal `Friday` or `Not specified` is not silently converted to a guessed date.

Manual action creation requires `meeting_id` and `task`; defaults are `owner=Unassigned`, no calendar date, `priority=Medium`, `status=Pending`. PUT accepts changed fields only: task, owner, due date/literal text, priority, status, notes and dependencies. Human changes preserve `source_snapshot`, set human provenance and do not receive a new AI support score.

List query examples:

- `/meetings?limit=25&offset=0&q=platform&status=completed`
- `/action-items?filter=My%20Tasks`
- `/action-items?filter=Overdue&sort=due_date`
- `/action-items?owner=Rahul&priority=High`
- `/action-items?meeting_id=...&status=Completed`

The exact supported query enums/defaults are shown in OpenAPI. Use URL encoding for names/filter values. Unknown enum values return validation errors rather than empty fabricated results.

Upload `multipart/form-data` with `file` and optional `meeting_id`. The API stores parse failures as failed document metadata while returning an actionable error. Attaching text can invalidate a meeting's old analysis; process it again. Deleting a document leaves previously copied transcript text, as clearly stated by the UI. Delete/edit the meeting to remove the copied source as well.

Search/ask accept:

```json
{
  "query": "Show all action items assigned to Rahul.",
  "limit": 8
}
```

Optional `meeting_id` narrows to an owned meeting. Ask also accepts bounded user/assistant `history`; system messages are forbidden. Returned answers include claims, source IDs, exact quotes, retrieval method, verification counts and insufficient-evidence state. Sources identify their real meeting/record, evidence location and current-record provenance. Retrieval scores are not probabilities.

## Errors and authorization

Errors use a stable structure:

```json
{
  "error": {
    "code": "not_found",
    "message": "Meeting not found"
  },
  "request_id": "server-generated correlation identifier"
}
```

Validation can add safe field-level details, without echoing input passwords or secrets. Typical statuses: 401 unauthenticated/expired/revoked; 404 missing or outside your ownership; 409 incompatible processing state; 413 oversized; 415 unsupported type; 422 invalid/malformed input; 429 quota exceeded; 503 unavailable provider/service. Unexpected errors return a safe generic message, not a stack trace or database credentials. Processing failures are also visible through their meeting's status endpoint.
