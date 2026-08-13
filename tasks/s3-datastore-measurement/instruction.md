<uploaded_files>/app</uploaded_files>

# Add S3 datastore-based usage measurement

Measurement configurations need a `"datastoreBased"` mode for S3 ingestion. Its `measurementConfiguration` contains `platform: "s3"` and the customer's string `accountId`; returned and persisted configuration also includes the generated `iamRoleArn`, `externalId`, `ingestion`, `dlq`, and `region` fields. Omitted platform and region default to `"s3"` and `"us-east-1"`. Creating a measurement must provision a uniquely named IAM role and policy scoped to that business's ingestion and DLQ prefixes, trusting the customer account with a fresh external ID. Updating the account must update role trust while preserving that role and external ID.

The internal S3 connector posts `{ message, s3Key }`, where `message` is one standard usage JSON record and the first `s3Key` segment is the business ID. Valid records must flow through the existing usage service with that business ID. Malformed records must be written to the configured DLQ under the mirrored source key plus `.message.text`, with the failed input and processing metadata; already-relative source keys must work too. Existing API-, agent-, and infrastructure-based measurement behavior must remain unchanged.

Preserve the existing integration boundaries used by this codebase: implement S3 provisioning on `DatastoreAccessInformation.setupAccess`, trust updates on `DatastoreAccessInformation.updateAccess`, orchestration in `MeasurementConfigService.create`, connector delivery on the exported `PrivateAPIUsageController.dbUsage`, and generic DLQ delivery on `StandardMeasurementEntity.publishFailureToDLQ`. Use `DB_MEASUREMENT_BUCKET_NAME`, `DB_MEASUREMENT_DLQ_BUCKET_NAME`, and `AWS_REGION`. The IAM role name is `datastore-<businessID>-<measurementId>`; its trust policy principal is `arn:aws:iam::<accountId>:root` and its external-ID condition must match the returned value. `dbUsage` passes the parsed record to `UsageService.create` with the business ID derived from `s3Key`.

Verify with:

    cd /app && npm run build && npm run test:ci -- --runInBand
