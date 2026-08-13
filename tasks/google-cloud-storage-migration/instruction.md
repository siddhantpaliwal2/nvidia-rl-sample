<uploaded_files>/app</uploaded_files>

# Migrate document storage to Google Cloud Storage

The document subsystem currently writes production uploads to Azure and records Azure as the default storage target. Add Google Cloud Storage as the destination for new production documents while keeping existing local, Azure, and S3-backed documents readable.

Add a Google storage target to the persisted storage enum and make it the default for newly constructed documents. Add upload and download helpers backed by the Google Cloud Storage SDK: uploads must preserve the caller's object path and bytes, downloads must return the stored bytes as an input stream, and blank paths must remain no-ops. The deployed runtime supplies its service-account resource on the classpath; do not add credentials, private keys, real documents, or production endpoints to the repository.

Keep the repository's compatibility API: add `Enums.StaticFileStorageTarget.GOOGLE`, default `new Document().staticFileStorageTarget` to it, and implement `HelperMethod.uploadObjectToGoogleCloudStorage(File, String)` plus `HelperMethod.downloadObjectFromGoogleCloudStorage(String)`. Obtain the configured Google `Storage` service through `StorageOptions`; use ambient/default credentials when the optional classpath service-account resource is absent. Upload with the requested path as the blob name and return success, and return a `ByteArrayInputStream` for downloads. `HelperMethod.downloadObjectFromLocalOrS3OrAzure(Document)` must retain local-file precedence, route explicit `AZURE` records to Azure, explicit `GOOGLE` records to the new helper, and otherwise preserve the S3 fallback.

Route non-development uploads to Google Cloud Storage. When downloading, continue to prefer an existing local file, retain the explicit Azure path for legacy documents, route persisted Google documents to the new backend, and preserve the existing S3 fallback for older records. Do not break the current Azure or local behavior.

Verify with:

    cd /app && sh /tests/test.sh
