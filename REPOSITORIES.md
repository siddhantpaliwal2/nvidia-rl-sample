# Evaluation substrates

The eight tasks in this sample use immutable pre-change snapshots from three
production enterprise repositories. Agents see a sealed working tree without
usable Git history; hidden tests enter the sandbox only at grading time.

## Usage-metering and billing backend

- **Stack:** TypeScript, NestJS, TypeORM, and Jest.
- **Domain:** usage metering and billing, offering/customer ownership,
  scheduled invoicing, wallets, and cloud usage ingestion.
- **Tasks:** dimension pricing tiers, top-up billing lifecycle, S3 datastore
  measurement, customer identity migration, and customer billing-schedule
  migration.
- **Environment:** each task uses its own exact pre-change commit. Node
  dependencies are preinstalled in the Daytona snapshot and grading runs
  deterministic unit tests.

## Email-campaign state machine

- **Stack:** TypeScript, Jest, and document-database repositories.
- **Domain:** managed email inboxes, campaign associations, deliverability,
  reputation, ranking, and Smartlead lifecycle integration.
- **Task:** email inbox infrastructure.
- **Environment:** external providers are mocked at existing service
  boundaries; no live email or Smartlead calls occur.

## Finbit fin360

- **Stack:** Groovy, Grails 2.3.11, and Java 8.
- **Domain:** heterogeneous bank-statement parsing and multi-backend document
  storage.
- **Tasks:** bank parser consolidation and Google Cloud Storage migration.
- **Environment:** the source-minimized parser snapshot contains only required
  parser/service code and pinned jars; the cloud snapshot contains 23
  allowlisted files. Real statements, service-account JSON, unrelated config,
  and the historical credential-bearing transfer script are excluded. Hidden
  verifiers use synthetic fixtures and deterministic boundary stubs.

## Shared properties

- Tasks start at the exact parent commit of a real feature or
  migration; no synthetic bugs are planted.
- Every task has an untouched-base reward of 0 and a reference-oracle reward
  of 1 under the same binary verifier.
- Source images and Daytona snapshots are distributed separately from this
  task package. Generated source patches may still require source-owner
  authorization before redistribution.
