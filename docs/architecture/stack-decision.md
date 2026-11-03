# Stack Decision

Date: 2026-10-30. Decision maker: the user (answers to three questions).

## Decisions

1. **Application stack:** a Python API plus a separate web interface.
   - Rationale: the document-processing and model-integration ecosystem; the interface progresses independently.
2. **Hosting:** managed cloud.
   - Rationale: keeping the operating cost at its lowest; backup and scaling stay with the provider.
3. **Language model:** a managed model service.
   - Consequence: data goes to the model provider; this must be stated in the privacy notice and the retention policy.

## Deferred Choices (at the relevant step)

- Relational database product.
- Semantic index product.
- Queue product.
- Cloud provider and concrete services.

## Effects

- The implementation skeleton is built in Python; the persistence abstraction is preserved (in-memory stores until a concrete database is selected).
- The model abstraction is designed on the managed-service assumption; the interface stays closed to provider changes.
