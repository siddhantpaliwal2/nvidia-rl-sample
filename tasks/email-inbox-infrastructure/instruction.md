<uploaded_files>/app</uploaded_files>

# Complete the email inbox infrastructure manager

Build the email-account subsystem used to assign warmed Smartlead inboxes to campaigns. An account is keyed by `smartleadInboxId`, retains its Smartlead client and email, derives its domain, tracks tags and campaign IDs, and exposes `numberOfCampaignAssociated`. Keep the numeric warm-up reputation as the deliverability score and expose its mapped band separately: score 100 is `High`, 98–99 is `Medium`, 95–97 is `Low`, lower scores are `Burned`, and a missing score is `Unknown`. Persist accounts in the email-account datastore and support create, lookup by ID/email/client, paginated listing, deletion, and idempotent campaign association. Treat repeated inbox IDs in one association request as a single inbox, and reject the entire request without writes if any requested inbox ID is missing.

When choosing inboxes for a campaign, compute the required pool as `floor(total emails / campaign days / emails per inbox per day)`, then rank that Smartlead client's inboxes by deliverability score descending, campaign count ascending, number of other inboxes on the same domain ascending, and creation time oldest first. Saving an inbox must hydrate its creation time and warm-up reputation from Smartlead and return a not-found error for an unknown remote inbox. Keep the controller/module wiring and the import/reputation-sync scripts usable, and preserve existing state-machine behavior.

Verify with:

    cd /app && npm run build && npm test -- --runInBand
