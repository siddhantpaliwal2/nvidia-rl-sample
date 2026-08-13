<uploaded_files>/app</uploaded_files>

# Add prepaid-credit top-up billing

Usage-based offerings need a `"topUp"` billing cycle backed by the existing customer wallet. The create and read contracts use string fields `topUpAmount` and optional `topUpThreshold`; the threshold defaults to `"0.2"`. A top-up amount is required for this billing cycle, top-up fields are invalid on other cycles, and subscription offerings cannot use it. Persist and return these fields without changing existing offering behavior.

Create one hourly scheduler per top-up offering. Enrollment and every hourly check must refill a wallet only when its balance is below `topUpThreshold * topUpAmount`, charging exactly the gap to `topUpAmount` through an invoice whose payment is stored as credit. Hourly usage must be deducted as a wallet transaction even when it exceeds the current balance; it must not generate a separate usage invoice. After the deduction, evaluate the refill using the updated balance. Preserve normal monthly and annual billing, invoice payment, and credit behavior.

Keep this behavior on the existing offering boundaries. A top-up offering must expose `topUp({ customer })`. Its hourly schedule must use `SupportedMeasurementFrequencies.everyHour`, carry `businessID` and `offeringId` in `scheduleParameters`, and use one stable offering-level `schedulerID` rather than a customer-specific ID. `topUp` must treat a balance exactly at the threshold as sufficient; below it, create one invoice with `storePaymentAsCredit: true` and one line item named `<offering name> - Top Up`, quantity `1`, and unit cost `topUpAmount - current balance`. The hourly path may use the existing `OfferingTopUpChecker` or the offering's billing flow, but it must record the full negative usage through `CreditService.create`, update the in-memory balance, and then call `topUp`. Zero usage still evaluates top-up but creates no credit transaction.

Verify with:

    cd /app && npm run build && npm run test:ci -- --runInBand
