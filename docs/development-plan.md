# Linevora Detailed Development Plan (Phases 1–3)

Source: analysis by specialist agents plus an adversarial reviewer. The
ordering is binding: correctness/security first (Phase 1), then
productization (Phase 2), and scaling only on a measured trigger
(Phase 3). Effort: S = 1–3 days, M = 1–2 weeks, L = 3+ weeks.

## Phase 1 — Pilot-Ready

Exit criterion: the Phase 1 acceptance tests plus a single green CI. No new infrastructure.

### P1.1 Grounding and Invariant 1 (M)
- extractor: the quote is verified as a normalized substring of the page text; a non-matching response is rejected.
- RequirementStore.add: page >= 1 and a quote are required (ValueError).
- A page+quote copy on MatchSuggestion; list_suggestions filters out records without a source.
- Acceptance: a fake model response with an invented quote produces no suggestion; a requirement without a source cannot be written; the quote survives on the suggestion of a deleted requirement.

### P1.2 Atomic Reprocessing (M)
- handle_process_version: all results are computed first and swapped in at a single point; on error the old state is preserved.
- An invalid LINEVORA_MATCHER value fails at startup.
- Acceptance: a matcher that blows up halfway does not corrupt the old suggestions.

### P1.3 Fail-Fast Persistence (M)
- In prod, startup stops when neither db_path nor snapshot_path is set.
- A corrupt snapshot is not silently swallowed; SQLite WAL + busy_timeout; a schema_version in the snapshot payload.
- Blob put is atomic (tmp + replace + fsync); get verifies integrity.
- Acceptance: there is no silent empty start with a corrupt backup.

### P1.4 Demo Data and Money (S)
- Demo prices/terms never become active automatically in prod (LINEVORA_SEED_DEMO, forced off in prod).
- Money math is done with Decimal (no rounding drift).
- Acceptance: on a fresh prod database a quote cannot be built with an unapproved price; cent-level tests hold.

### P1.5 Ownership and Hardening (M)
- Inquiry carries created_by (the ownership record). Note: the current test contract defines the viewer as a team-internal read-only role; the cross-tenant restriction arrives with Phase 3 (Tenant) — for the pilot, role checks within a single team are sufficient.
- Upload streaming size limit, magic-byte checks and a PDF page limit.
- Plain-text passwords rejected in prod; the demo model is off in prod; the login hint is removed.
- Acceptance: a large file is rejected without being loaded into memory; the ownership field is populated on all records.

### P1.6 CI and Honest Eval (M)
- GitHub Actions: pytest + eval (scripted = smoke) + node --check; make check.
- A golden set (human-labelled) seeds Phase 2; the real-model gate is nightly/manual.
- Acceptance: no merge without green CI.

## Phase 2 — Productization

Exit criterion: the specialist team does its daily work in the panel, leaving a trace.

### P2.1 Suggestion Decisions and Corrections (L)
- PATCH suggestion accept/reject/override; requirement correction; every decision audited.
- Gap answering; a quote is blocked while a mandatory gap is open.
- An alternative "use this" action; decisions feed the eval/synonym pool.
- Acceptance: a rejection with a rationale from the panel is visible in the audit log; a quote is blocked on a mandatory gap.

### P2.2 Source Viewer and PDF (M)
- export.pdf is wired into the UI; a preview does not change status, an official export does.
- Quote highlighting and clickable citations; router_ui cache headers; a print stylesheet.
- Acceptance: one-click PDF download; a preview does not corrupt status.

### P2.3 Panel Resilience (M)
- Persistent session + revoke usage, hash deep-linking, focus-preserving rendering, loading/AbortController, an accessibility package (labels/aria/dialog/focus).
- List search/filter/pagination; return reasons; catalog editing.
- Acceptance: the session survives a refresh; 100+ audit records are paginated.

### P2.4 Persistence v2 (L)
- Row-based writes, unit-of-work, get() returns a copy, cursor pagination.
- Encrypted/checksummed scheduled backup; a restore drill with RPO/RTO targets.
- Acceptance: on a 10k catalog, a mutation is not bound to O(N) JSON (benchmark).

### P2.5 Model Cost and Quality (M)
- Token/$ metering, a per-inquiry budget, backoff retries, page chunking.
- Unit/range normalization; matcher A/B on the golden set, threshold calibration.
- Acceptance: extraction F1 and Recall@3 are reported; cost is visible in metrics.

## Phase 3 — Scaling (only on a trigger)

- P3.1 PostgreSQL + Alembic. Trigger: a multi-worker need / SQLite lock measurements.
- P3.2 A durable queue + pipeline separation. Trigger: queue loss/latency measurements.
- P3.3 A real embedding index (pgvector/faiss). Trigger: lexical insufficiency on the golden set.
- P3.4 Tenant/SSO/erasure. Trigger: a second customer or a contract clause.
- P3.5 Containers/IaC, Prometheus/OTel, SLO/load testing. Trigger: an SLA commitment.

## Decisions

- D1 Persistence: Phases 1–2 on SQLite (WAL); PostgreSQL on the Phase 3 trigger.
- D2 Identity: HMAC + ownership is sufficient for the pilot; JWT/OIDC on an SSO request.
- D3 Money: Decimal, non-negotiable and immediate.
- D4 Matcher: Lexical by default; the decision by golden A/B; an invalid value fails fast.
- D5 Model: the single-provider abstraction is not grown; a usage field is added now.
- D6 Export: the preview ≠ official-export distinction lands in Phase 2.
- D7 Privacy: the data flow to the model provider gets a written decision before the pilot contract.

## Anti-Goals (not before the pilot)

A PostgreSQL migration, Celery/DLQ, a separate embedding service, Tenant/SSO/KMS, an IaC/SLO program, an 85% coverage gate, microservices, an SSR frontend rewrite.

## Status

- [x] Phase 1 (implemented; acceptance tests in tests/test_phase1.py)
- [x] Phase 2 (core implemented; acceptance tests in tests/test_phase2.py. Note: the /metrics response shape is fixed by the current test contract; the token estimate is exposed as CallRecord.estimated_tokens. Panel JS syntax is verified in CI with node --check. Completion: copy-safety on store get/list, row-based incremental SQLite writes (store_rows), source-quote highlighting, the /v1/metrics/model-usage endpoint; tests in tests/test_phase2_completion.py.)
- [~] Phase 3 (core implemented; tests in tests/test_phase3.py)
  - P3.1: the migration runner + LINEVORA_DB_URL (sqlite) are active; the PostgreSQL DDL is ready; the live repository awaits psycopg plus a trigger.
  - P3.2: the pipeline service is split out; job recovery + backoff + GET /v1/jobs/dead-letter are active.
  - P3.3: EmbeddingMatcher + HttpEmbedder are active (LINEVORA_MATCHER=embedding).
  - P3.4: tenant isolation (a 4th field on the user record) + DELETE erasure are active; SSO/OIDC was not implemented because it requires an IdP choice.
  - P3.5: Dockerfile/compose, the Prometheus endpoint, readiness and scripts/load_test.py are ready; Docker is absent on this machine and a live bind could not be verified due to the sandbox.
