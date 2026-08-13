# Reference plan and fairness notes

## Production provenance

- Source workstream: ENG-411 and children ENG-439, ENG-445, ENG-446, ENG-499, and ENG-500.
- Historical implementation: Paigo PRs 114, 115, 116, and 118 across 3 days; ClickUp activity spans 17.8 days.
- Base: `cc633c6ae18b59698d5b9606f3b0aac2e5b4baf9`.
- Oracle head: `95c1547981bf230482eeec022c23de9246a64523`, filtered to the measurement/usage surface, plus DLQ key and awaited-write corrections.
- Packaged production scope: 19 files and about 1,800 changed lines including the dependency lock; generated docs and integration fixtures are excluded.

## Behavioral surface

1. Add and validate the datastore-based S3 configuration mode.
2. Provision scoped IAM policy/role access with fresh external IDs.
3. Persist and return all access and endpoint fields; preserve identity on trust updates.
4. Route connector-delivered standard usage records to the existing usage path.
5. Mirror malformed source records into the DLQ with diagnostic metadata.
6. Preserve existing measurement modes and usage APIs.

## Verifier design

The verifier exercises DTO nesting, entity persistence/read-back, IAM request semantics, service orchestration, connector routing, and DLQ writes with deterministic mocks. AWS and database calls never leave the test process. It accepts any source layout or helper design that produces the stated public objects and boundary calls; it does not inspect file names, class names, exact error text, or oracle similarity.

The connector contract is stated explicitly because the backend receives already-separated records rather than parsing S3 files itself. The historical DLQ writer duplicated the business prefix and did not append the ticket-required suffix; the packaged oracle corrects both behaviors.
