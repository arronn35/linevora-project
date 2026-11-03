# Operations: Backup, Security, Pilot Acceptance

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LINEVORA_ENV` | `dev` | `dev` or `prod`. In `prod` the signing key and users are mandatory; otherwise the app will not start. |
| `LINEVORA_SECRET_KEY` | development value | Token signing key. A strong, unique value is required in production. |
| `LINEVORA_TOKEN_TTL` | `3600` | Token lifetime (seconds). |
| `LINEVORA_USERS` | development users | `name:password:role,...` form. Roles: `admin`, `specialist`, `viewer`. |
| `LINEVORA_BLOB_DIR` | `var/blobs` | Immutable store for original files. |
| `LINEVORA_SNAPSHOT_PATH` | (none) | When set, loaded at startup; saved via `POST /v1/admin/snapshot`. |

## Backup and Restore

Durability has two parts: the snapshot file (all records) and the file
store (`blob_dir`). Back both of them up together.

1. Save: `POST /v1/admin/snapshot` (admin only). The response is `{"saved": true, "path": ...}`.
2. Copy: copy the snapshot file and the `blob_dir` contents to backup media.
3. Generations: on each save the previous file is kept as `.1`–`.5`; the sixth generation is deleted.
4. Restore: put the backup files back in place and restart the application; they are loaded automatically at startup.

Restore drill (automated in `tests/test_snapshot.py`): save → back up →
change → restore the backup → load → the old state is verified.

## Retention Policy (pilot)

- Audit records: append-only, never deleted; retained indefinitely during the pilot.
- Inquiry files: content-addressed, immutable; retained while the customer relationship lasts.
- Snapshot generations: the last 5 saves; older ones move to operations backups.
- Data sent to the model provider: under the managed-service decision, inquiry texts are transmitted to the provider; this is declared to the customer in the privacy notice.

## Security Notes

- `LINEVORA_ENV=prod` is mandatory in production; the app will not start with the default key/users.
- Roles: price/terms and product definition are `admin` only; quote preparation is `specialist` and above; approval and return are `admin` only; reading is all roles.
- An unapproved quote cannot be exported; this rule is enforced in the data layer.
- All decision operations are written to the audit log (`GET /v1/audit`, admin only).
- Responses carry security headers (`nosniff`, `DENY`, `no-referrer`).
- Arriving with the persistence step: password hashing (the `pbkdf2_sha256$...` form is supported; plain text only for backward compatibility), a rate limit on the token endpoint (`LINEVORA_RATE_LIMIT_PER_MINUTE`), token revocation (`POST /v1/auth/revoke`), PDF quote output (`GET /v1/quotes/{id}/export.pdf`), SQLite persistence (`LINEVORA_DB_PATH`).
- Known limits (after the pilot): key rotation, cross-process persistence of the revocation list, sending metrics to an external monitoring system, measuring model accuracy on real historical inquiries (the eval set is currently representative).

## Observability

- `GET /v1/metrics` (admin only): HTTP counters, job statuses, model call counts, quote statuses and average approval time.
- Every response carries `X-Request-ID`; the request log (the `linevora.http` logger) includes the method, path, status and duration.
- Matching changes are not shipped before passing the eval gate:
  `python eval/run_eval.py --cases eval/cases --extractor scripted --min-score 0.8`.

## Pilot Acceptance Checklist

- [ ] Pilot team and 10–20 historical inquiries plus a catalog sample are ready.
- [ ] `pytest -q` is green; the eval gate is at threshold (`--min-score` to be settled with the pilot).
- [ ] Startup verified with `LINEVORA_ENV=prod`, a strong key and real users.
- [ ] A backup + restore drill has been run in the real environment.
- [ ] Quote time, first-quote accuracy and correction rate are measured (`/v1/metrics`).
