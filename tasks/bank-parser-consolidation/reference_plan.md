# Reference plan

1. Inventory the duplicated bank utility and service entry points and identify which layouts already match the shared parser's table contracts.
2. Harden shared date, header, description, amount, and continuation-row handling before moving adapters onto it.
3. Route compatible bank services to the shared entry points while retaining the explicit Andhra regex and Bank of Baroda saving-account fallbacks.
4. Move common basic-detail behavior into the shared bank utility and leave only institution-specific account-holder extraction behind.
5. Exercise both HTML layouts with synthetic statements, including OCR-corrupted dates, blank descriptions, balance-only continuation rows, and stable legacy routes.
