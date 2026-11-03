# Linevora Technical Architecture — Overview

Status: design document. The technology product has not been selected yet; a stack decision is required before moving to the implementation steps (see "Selection Criteria").

Source: the product description (the inquiry-to-quote flow, source showability, team approval, approved prices/terms) and the architectural plan.

## Architectural Approach

A modular whole with clear boundaries: a single deployment unit with sharp internal module boundaries. Document processing runs over an async pipeline; language-model calls sit behind a replaceable abstraction. Rationale: for a small team at an unvalidated product stage, the operating cost of a distributed architecture produces no value; when the boundaries are drawn correctly, the parts can be made independent later.

## Components

1. **Team web interface.** Responsibility: viewing inquiries, reviewing/correcting matches, reports, quote approval. Interface: talks only to the application API layer; the source section a suggestion relies on is visible in one click on every screen.
2. **Application API layer.** Responsibility: the single entry point; identity, authorization, input validation, audit logging. Interface: serves clients and internal modules over HTTP; contains no business logic.
3. **Document processing pipeline.** Responsibility: file intake, text extraction (page/section structure preserved), requirement extraction, matching, report generation. Interface: writes jobs to a queue, workers run the steps; every step's status, error and retry are tracked.
4. **Language-model abstraction.** Responsibility: making all model calls through a single internal interface, validating outputs against a schema. Interface: changing the provider does not affect the interface; a response that does not fit the schema never enters the pipeline; every extraction carries a source pointer.
5. **Business-records database.** Responsibility: inquiry, version, requirement, match, approval, quote and audit records. Interface: modules write only to their own aggregate; version and audit records cannot be deleted, only appended.
6. **Semantic search index.** Responsibility: producing catalog candidates for inquiries written with different terminology. Interface: returns a candidate list plus scores; it does not make the final decision; score thresholds are configurable.
7. **File store.** Responsibility: immutable storage of original inquiry files and generated quote documents. Interface: write/read by content address; records in the database point to files.
8. **Catalog and price/terms module.** Responsibility: product records, synonyms, features; versioned prices and terms. Interface: gives the quote engine only the active version; older quotes stay bound to the version they were produced with.
9. **Quote engine and approval flow.** Responsibility: draft generation from approved inputs, correction/approval steps, document output. Interface: produces no output without an approval record; this rule is enforced in the data layer.
10. **Observability.** Responsibility: logging, metrics, request tracing, model call count/cost tracking, step durations. Interface: pilot metrics (quote time, correction rate) are fed from here.
11. **Evaluation set and gate.** Responsibility: a fixed test set built from historical inquiries; matching changes are not shipped before being measured on the set. Interface: a repeatable measurement; a result below the threshold stops the release.
12. **Security foundation.** Responsibility: encryption in transit and at rest, role-based authorization, backup and restore, retention policy.

## Data Flow (end to end)

1. The team uploads the inquiry file/text → it is written to the file store, and an inquiry plus version are opened in the business records.
2. The processing pipeline extracts the text and produces requirements; every requirement carries a source pointer.
3. The semantic index provides candidates; match suggestions are recorded with a score, a rationale and a source.
4. The missing-information list, the version diff (if any) and alternative suggestions are produced.
5. The team reviews, corrects and approves; all decisions are written to the audit log.
6. The quote engine produces a draft with the active price/terms version; after approval, the document output is taken.

## Non-Negotiable Rules

1. A suggestion without a source is not shown to the user.
2. No quote is exported without team approval.
3. A quote uses only versioned, approved prices/terms.

The enforcement points are in `data-model.md`.

## Rejected Alternatives

- Splitting into distributed services at the start: operating cost, unnecessary at an early stage.
- Code directly dependent on a model provider: lock-in and cost risk.
- Processing documents synchronously: long waits, no fault tolerance.

## Technology Selection Criteria (no product names)

- Application language/framework: the team's fluency, the document-processing and model-integration ecosystem, the hiring pool.
- Relational database: transactional integrity, fit with version/audit patterns, backup ease.
- Semantic index: threshold adjustability, reindexing cost, hosting cost.
- Queue/worker: retries and visibility, operating cost.
- File store: immutability, access control, cost.
- Model provision: accuracy, call cost, data-residency constraints.
- Hosting: start from the lowest operating cost.

## Step Status

- [x] Step 1: data model and non-negotiable rules (`data-model.md`)
- [x] Step 2: API skeleton + identity and authorization (`src/linevora/api`, `auth`, `audit`)
- [x] Step 3: file store and import (`files`, `ingest`, `inquiries`)
- [x] Step 4: model abstraction + eval set (`model`, `eval`)
- [x] Step 5: processing pipeline and matching (`jobs`, `matching`, `catalog`)
- [x] Step 6: gap/diff/alternative reports (`reports`)
- [x] Step 7: quote engine and approval flow (`quotes`)
- [x] Step 8: observability and security hardening (`observability`, `docs/operations.md`)
- [x] Step 9: persistence (SQLite), a real model adapter, semantic matching, security hardening (hash/rate-limit/revocation), PDF output (`persistence`, `model/client.py`, `matching/vector_matcher.py`, `auth/passwords.py`, `quotes/pdf.py`)
