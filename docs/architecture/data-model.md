# Data Model and Non-Negotiable Rules

## Entities

- **User:** identity, name, role (roles: admin, quote specialist, read-only). Role changes are written to the audit log.
- **Product:** code, names, synonyms, features (a name/value list), unit. The catalog's main record.
- **PriceVersion:** product → price, currency, validity range, status (draft / active / archived). A product can have only one active version.
- **TermsVersion:** a set of terms (delivery, payment, validity, etc.), validity range, status (draft / active / archived). The single-active-version rule applies.
- **Inquiry:** customer, title, status (open / in quote / closed).
- **InquiryVersion:** inquiry → version number, source-file pointer, extracted text, page/section structure. Carries a link to the previous version.
- **Requirement:** version → product type, features, quantity, unit, tolerances, **source pointer (required: file + page/section + quote)**.
- **MatchSuggestion:** requirement → product, score, rationale, source pointers (required), status (pending / approved / rejected / corrected), reviewer, time.
- **InformationGap:** requirement/version → field, question text, mandatory flag, status (open / answered / waived).
- **VersionDiff:** old version → new version, change lines (field, old value, new value).
- **AlternativeSuggestion:** requirement → product, criterion comparison, rationale, status (pending / approved / rejected).
- **Quote:** inquiry → status (draft / in_review / approved / exported), prepared by, approved by, timestamps.
- **QuoteLine:** quote → product, quantity, **the PriceVersion id in effect when it was produced (pinned)**, amount. The quote also carries the **TermsVersion id**.
- **StoredFile:** original name, content address, integrity hash. Cannot be changed after being written.
- **AuditRecord:** time, actor, action, object, before/after summary. Append-only; cannot be updated or deleted.

## State Machines

- Quote: draft → in_review → approved → exported. Returns (in_review → draft) happen through the audit log; there is no approved → draft transition — a new draft version is opened instead.
- MatchSuggestion and AlternativeSuggestion: pending → approved / rejected; on an approved suggestion, a later change requires a new decision that leaves a "corrected" trace instead of an edit.

## Enforcement Points for the Invariants

1. **No suggestion without a source is shown.** The source pointer cannot be left empty on Requirement and MatchSuggestion records (required at write time); the read layer does not list a record without a pointer. Validation: an attempt to write a record without a pointer is rejected.
2. **No export without approval.** Document output is produced only from a quote whose status is "approved"; the export writes the approver identity and time to the audit log and sets the status to "exported". Validation: an output attempt from an unapproved quote is blocked.
3. **Only approved prices/terms.** When a quote line is written, the product's active PriceVersion is resolved and its id is pinned to the line; the active TermsVersion is pinned to the quote. A product without an active version cannot enter a quote line. Validation: after a price change, an older quote keeps showing the values of the version it was first produced with.

## Integrity Notes

- Version and audit records are append-only; a correction is made with a new record.
- The match between content in the file store and pointers in the database is checked by a regular verification job.
- Score thresholds and mandatory-field lists live in configuration, not hard-coded.

## Acceptance Checklist

- [ ] An attempt to write a requirement/suggestion without a source pointer is rejected.
- [ ] A document-output attempt from an unapproved quote is blocked.
- [ ] After a price/terms change, an older quote preserves the values of its original version.
