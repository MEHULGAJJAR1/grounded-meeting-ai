# Security and privacy notes

## Implemented controls

- JWT signature, expiry, issuer/audience and revocation/version checks; bcrypt password hashes, never plaintext storage.
- Explicit current-user predicates and owned-resource resolution for meetings, documents, actions, exports, risk/question updates and retrieval. Foreign resource identifiers return 404.
- Pydantic v2 request and strict AI schemas; final intelligence validation after verification. Unknown fields/system history roles and malformed confidence values are rejected.
- ORM-bound queries rather than concatenated user SQL. Source IDs in answers must belong to the returned scoped source set.
- Upload byte, extension/magic/content and parser limits; controlled private storage names, safe downloads, PDF encryption/scanning errors and bounded DOCX decompression.
- Structured request/process logs without bearer headers, credential values, request bodies, query strings or transcript text. API errors do not echo private input or internal traces. Settings hide validation input values.
- Environment-only keys and SMTP/database credentials. Development secrets are generated, private `.env` is ignored, and the release ZIP excludes runtime data/credentials/dependencies.
- Explicit CORS origins; production rejects wildcard CORS, enabled sample bootstrap and short JWT secrets.
- Private filesystem downloads, guarded SPA path resolution, safe XML/PDF escaping and CSV formula-prefix protection.
- In-process request limits on auth, processing, uploads and retrieval.
- Transcript/document content is untrusted data in extraction, verification and RAG prompts. No LLM database/OS tools are exposed. Evidence checks are deterministic in addition to independent model verification.
- Original extraction and human action changes are distinguished rather than falsely source-verifying a user-entered assignment.

## Deployment responsibilities

The provided setup is a production-style portfolio application with a single API worker, not a hardened multi-replica cloud service. Use HTTPS, restricted proxy/backend access, trusted forwarded-header configuration, encrypted disks/backups, private volume permissions, shared quotas for scale and operational monitoring. Never expose PostgreSQL directly to the internet. Production Compose disables development sample routes.

JWTs live in browser sessionStorage, not persistent localStorage; protect the frontend against XSS and extensions. An HttpOnly-cookie/CSRF design or SSO/MFA is a possible future authentication deployment. Email verification/organisation membership are not implemented; do not enable unrestricted SMTP onboarding publicly without an appropriate recipient-verification policy.

Configured OpenAI calls transmit relevant source/question content to OpenAI. Choose an appropriate provider/privacy policy for your meeting data. The application does not add third-party analytics or CDN resources. Assistant conversations are not persisted server-side.

A copied upload becomes part of a meeting transcript. Deleting its original file does not silently delete the copied transcript or human-managed actions; the interface discloses this behavior. Meeting deletion cascades its private derived records. Metadata-only audit events can remain for account auditability; they do not contain transcript bodies or passwords.

Independent verification reduces unsupported assertions but does not make arbitrary LLM discourse infallible. Literal/pattern local checks are more limited than semantic entailment. Scores are heuristics, not guarantees. Review original quotes for high-stakes decisions, possible source mistakes or prompt-injection content.

## Reporting and validation

Reproduce automated tests using README commands. Check `docs/VERIFICATION.md` for actual executed validation and clear unverified integrations. Dependency audit results describe the known-vulnerability databases at the validation date; they cannot guarantee absence of all vulnerabilities. Use your hosting provider's private security-reporting channel for a deployed instance; do not publish private transcripts, tokens or environment files in a public issue.
