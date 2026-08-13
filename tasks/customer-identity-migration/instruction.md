<uploaded_files>/app</uploaded_files>

# Migrate service ownership to customers

Deprecate `serviceId` and `applicationId` as the public ownership boundary for offerings and usage. A customer may instead carry an optional UUID `offeringId`; persist it and return both the ID and the hydrated offering from customer reads. An offering that is still referenced by any customer must not be deletable, while customer deletion must no longer be blocked merely because legacy service records exist.

Move usage reads to `GET /customers/:customerId/usage`. Preserve the existing start, end, and aggregation-interval query behavior. Resolve dimensions from the customer's offering and aggregate every query with that `customerId`. If the customer has no offering at this stage of the migration, reject the usage request as a conflict. Remove the public service controller surface; legacy service internals may remain where other modules still require them.

Keep the public flow on the repository's established methods: `UsageService.findUsageForCustomer({ customerId, businessID }, query)` must load the customer and its hydrated offering, pass `customerId` as both the customer filter and legacy aggregation `clientID`, and apply query time/interval overrides to every offering dimension. `CustomerService.findOne` must return invoices plus the hydrated `offering`, and `CustomerService.findUsageForCustomer` must wrap the unchanged usage array as `{ data, message: "Found usage" }`. `PublicAPICustomerController.findUsage` must forward the business ID, route customer ID, and query object to that service method.

The standard usage contract now requires `customerId` instead of `serviceId` or `applicationId`. Persist and restore that field on every standard measurement, use it in Influx tags and aggregation filters, and map agent/Kubernetes label `paigo_customer_id` to it together with `paigo_dimension_id`. Update dependent modules and infrastructure gatherers so the application builds and existing non-migrated behavior remains intact.

Verify with:

    cd /app && npm run build && npm run test:ci -- --runInBand
