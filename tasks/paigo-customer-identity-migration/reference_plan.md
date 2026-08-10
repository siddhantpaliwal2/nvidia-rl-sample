# Reference plan and fairness notes

## Production provenance

- Source epic: ENG-504, "ServiceId Deprecation", especially ENG-505 through ENG-509 and ENG-511.
- Historical implementation: PRs 139 and 141, from March 9 through March 11, 2023.
- Base: `8ff3f0c2948ca052385ec4bafc4ebb8291f78fa9`.
- Oracle head: `b933efd140d3d2cf50de814ec2cfacad873e069d`.
- Historical change: 66 files, +944/-1,316; the production oracle excludes tests and generated documentation.

## Behavioral surface

1. Move offering ownership from services to customers across DTO, entity, persistence, and read paths.
2. Expose customer usage with the existing time and aggregation overrides.
3. Attribute standard and infrastructure-derived measurements to customers in storage and queries.
4. Protect referenced offerings, remove the service deletion constraint from customers, and retire public service routes.
5. Rewire dependent Nest modules without breaking the existing application.

## Verifier design

The hidden verifier exercises entity round trips, measurement conversion, infrastructure preprocessing, customer usage delegation, hydrated reads, controller forwarding, and offering reference protection with offline mocks. It checks observable fields and calls, not exact messages, file locations, class layout, source similarity, or the historical implementation strategy.
