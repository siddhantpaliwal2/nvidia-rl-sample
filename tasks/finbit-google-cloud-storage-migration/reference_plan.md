# Reference plan

1. Add the pinned Google Cloud Storage SDK dependency used by this Grails application.
2. Extend the persisted storage-target enum and change only the new-document default to Google.
3. Implement credential-resource-backed Google upload and download helpers with safe blank-path behavior.
4. Switch production uploads to Google while retaining the local development path.
5. Route downloads by the document's persisted target, preserving local precedence, Azure compatibility, and the S3 fallback.
6. Exercise the migration with synthetic byte payloads and no real customer files or credentials.
