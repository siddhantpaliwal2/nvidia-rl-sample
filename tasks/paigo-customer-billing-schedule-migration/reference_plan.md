# Reference plan and fairness notes

## Production provenance

- Source epic: ENG-504, "ServiceId Deprecation", especially ENG-510, ENG-512, ENG-513, and ENG-514.
- Historical work: the second half of PR 140, March 11 through March 15, 2023.
- Base: `b933efd140d3d2cf50de814ec2cfacad873e069d`.
- Oracle head: `8936ec462cbe4e405088f03ce5b80a9f8c9d4a26`.
- Historical interval: 4 days, 56 touched files and +1,447/-855 including integration tests and docs; the production-only oracle is a 23-file cross-module change.

## Behavioral surface

1. Create and replace billing schedules at customer enrollment boundaries.
2. Consume scheduler jobs with customer identity and the offering's billing period.
3. Generate usage-total invoices and persist their billing ledger records.
4. Route billing and measurement jobs to separate queues.
5. Make unenrolled-customer usage reads empty and preserve existing data scheduling.

## Verifier design

The hidden verifier uses offline service tests with mocked Influx, queues, customers, invoices, and schedules. It grades scheduler conditions and payloads, invoice boundaries, persisted billing identity, queue selection, and unenrolled usage behavior. The migrated customer and invoice mocks expose both boundary methods in either constructor position so Nest dependency ordering is not graded. Exact log or error text, helper names, source layout, and historical code shape are not graded.
