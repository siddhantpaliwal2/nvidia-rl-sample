# Reference plan and fairness notes

## Production provenance

- Source work item: ENG-830, "Dimension Pricing Tiers".
- Historical implementation: paigo-backend PR 349, 14 commits over 3 days.
- Base: `b86196fd83b19f092c484eabf303e04a62986611`.
- Oracle head: `fc8f14b6f27dae6e42cedbb7101fdc322be43a8f`, plus a one-branch correction that rejects an `"inf"` bound before the final tier.
- Historical change: 22 files, +2,667/-42; the production-only oracle excludes tests, generated API documentation, fixtures, and CI.

## Behavioral surface

1. Validate the tier schema, ordering, increment alignment, infinity sentinel, and required prices.
2. Keep tier fields mutually exclusive with the legacy flat-price contract.
3. Round-trip tiers through create, read, replace, and clear operations.
4. Allocate usage across ordered tier ranges and emit separate invoice lines.
5. Preserve free-first-tier, usage-increment, currency, and price-precision behavior.
6. Preserve non-tiered billing and unrelated offering behavior.

## Verifier design

The hidden patch combines the production PR's billing-entity tests with focused offline contract tests at the existing DTO and persistence boundaries. The score gate selects tier allocation, validation, serialization, read-back, replacement/clear shapes, and unchanged billing regressions. Tests assert validation outcomes, persisted values, and invoice line items; they do not inspect class names, file names, commit identity, or textual similarity to the oracle.

The prompt deliberately omits implementation locations while spelling out the graded behavior and exact public JSON field names. An alternative implementation may use different DTOs, validators, storage representation, or billing helpers as long as the visible contract and regressions pass.

The historical branch accepted an infinite bound followed by a finite bound because `parseFloat("inf")` produced `NaN`. The packaged oracle closes that ticket-visible edge case, and the verifier identifies the specific validation result rather than accepting an unrelated failure.
