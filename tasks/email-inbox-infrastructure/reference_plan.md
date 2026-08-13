# Reference plan and fairness notes

## Production provenance

- Source work item: CHAMP-2197, "complete email inbox infra manager".
- Historical implementation: state-machine PR 16, 9 commits over 4 days.
- Base: `26d8b5c4f248e8d27413f1fc0b0bbf0e24d00beb`.
- Oracle head: `75cb7c2008a2821a0bca77477916a48e7be3fe99`.
- Historical change: 20 files, +1,125/-87; the production-only oracle excludes tests and CI.

## Behavioral surface

1. Normalize Smartlead inbox identity, domain, deliverability, tags, and campaign counters.
2. Persist and retrieve accounts through the existing datastore abstraction.
3. Associate campaigns idempotently and reject partial ID sets atomically.
4. Compute pool size and express the four-factor mailbox ranking in the datastore query.
5. Hydrate new accounts from Smartlead and preserve explicit not-found behavior.
6. Retain controller/module and operational import/synchronization paths.

## Verifier design

The hidden verifier runs entirely against mocked datastore and HTTP boundaries. It checks returned domain objects and observable persisted state rather than MongoDB internals, repository or entity file placement, pagination-envelope shape, an `id` alias for the documented `smartleadInboxId` key, exact no-op write counts, or a particular mapped-band property alias. Nest constructor metadata selects the candidate's actual datastore or repository dependency instead of guessing from export names. The fake datastore supports exact, `$in`, and `$exists` inbox-ID queries, page-count requests, missing-ID lookups, and Smartlead hydration during either service- or entity-level persistence. The prompt publishes the ranking order, numeric-score/band distinction, duplicate-ID behavior, and atomic rejection semantics that the tests require. Existing pure email-template tests provide regression coverage.

The historical PR's service spec required a live MongoDB process. It is intentionally not used for grading; the replacement contract tests exercise the same service/entity behavior without network or daemon dependencies.
