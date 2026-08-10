# Reference plan and fairness notes

## Production provenance

- Source work item: ENG-1167, "Top-up as a payment schedule".
- Historical implementation: 21 commits over 6 days; ClickUp activity spans 18.5 days.
- Base: `bbad236ac1116d756576fa98efba49f8f8fd3bce`.
- Oracle head: `5c4eacae2c1b65c2f1dc7b3e68df89a5afeb6e5c`, plus corrections for string wallet balances and usage deductions that never create usage invoices.
- Historical change: 35 files, +1,569/-325; the production-only oracle excludes tests and test fixtures.

## Behavioral surface

1. Extend offering DTO, entity, persistence, and read paths with the top-up cycle and fields.
2. Enforce cycle/type compatibility and the default threshold.
3. Create a stable hourly offering scheduler and preserve existing customer schedules.
4. Fill a wallet to its configured target on enrollment or after crossing the threshold.
5. Deduct hourly usage from wallet credit, including overdraft usage, without issuing usage invoices.
6. Preserve normal billing and payment behavior outside top-up offerings.

## Verifier design

The hidden verifier uses offline DTO/entity tests and direct service tests with mocked storage, scheduler, invoice, and credit boundaries. It checks validation outcomes, persisted/read values, scheduler inputs, invoice line items, wallet transactions, and absence of usage invoices. It does not require historical class names, file placement, exact validation text, source similarity, or a particular helper decomposition.

The prompt exposes every graded public field and the observable wallet/invoice lifecycle. The historical branch represented wallet balance inconsistently and could create an hourly usage invoice when credit was insufficient; the packaged oracle and tests correct those ticket-visible failure modes.
