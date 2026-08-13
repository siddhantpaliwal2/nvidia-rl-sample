<uploaded_files>/app</uploaded_files>

# Complete the customer billing-schedule migration

Finish the service-to-customer migration for recurring billing. Creating a customer must create a monthly billing schedule only when that customer has an offering. When an existing customer gains or changes an `offeringId`, replace any previous billing schedule with a customer-level schedule; an already-missing old schedule is not an error. Preserve the authenticated subject and business ID in the scheduler configuration.

Billing jobs receive `businessID` on the scheduler record and `customerId` in `scheduleParameters`. Resolve the customer and its offering, derive the offering billing-cycle time range, call the existing usage-total invoice path with that exact customer and range, and persist a billing record containing the returned invoice ID. Report processing failures through the existing audit channel instead of leaving the queue job with a partially stored billing record.

Route billing scheduler emissions to `scheduler_billing_queue` with the `billingReport` consumer name. All non-billing measurements must continue to use the normal scheduler queue and their dimension consumer. Finally, a usage read for a customer without an offering should return an empty result rather than fail.

Verify with:

    cd /app && npm run build && npm run test:ci -- --runInBand
