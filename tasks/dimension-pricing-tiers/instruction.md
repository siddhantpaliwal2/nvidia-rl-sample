<uploaded_files>/app</uploaded_files>

# Add volume-based pricing tiers to usage dimensions

Usage dimensions need an optional `tiers` array so high-volume usage can be billed at different unit prices. Each tier uses string fields `tierPosition`, `upperBound`, optional `tierName`, and optional `unitPrice`; `upperBound` is a numeric string or `"inf"`. Bounds must increase without overlap, align to `usageIncrement`, and leave `"inf"` only at the end. Every tier after the first requires `unitPrice`; an omitted first-tier price represents a free tier.

Tiered dimensions are mutually exclusive with `usageEntitlement`, `consumptionPrice`, and `overageAllowed: true`. Creation, update, and read APIs must validate, persist, replace, clear with `tiers: null`, and return the same tier objects. Billing must sort by numeric `tierPosition`, allocate usage across the inclusive bounds, divide quantities by `usageIncrement`, preserve price precision and currency conversion, and produce a distinct line item per consumed tier. Append `tierName` to the normal line-item name when present. Existing non-tiered dimensions and invoice behavior must remain unchanged.

One legacy case is especially important: a dimension with no `tiers`, no `consumptionPrice`, and no `usageEntitlement` is valid and contributes no invoice line items. Do not make tier support turn that unpriced dimension into an error or a synthetic charge.

Verify with:

    cd /app && npm run build && npm run test:ci -- --runInBand
