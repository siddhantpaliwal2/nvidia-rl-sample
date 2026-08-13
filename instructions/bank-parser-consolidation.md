# Consolidate heterogeneous bank statement parsers

The bank-statement subsystem has accumulated duplicated parsing paths for individual institutions. Consolidate the common PDF-to-table behavior so the shared bank parser handles the overlapping formats used by Andhra Bank, Bank of Baroda, City Union Bank, HSBC, Karur Vysya, Kotak, Oriental Bank of Commerce, Punjab National Bank, and the existing generic consumers. Keep truly bank-specific fallbacks only where their formats still require them.

The shared parser must remain tolerant of real statement noise. Month-name dates may contain spaces, optional hyphens, or no separators; normalize them consistently, including the known `JUY` OCR error for July. Recognize opening-balance and repeated transaction-header rows, retain a dated transaction even when its description cell is blank, and preserve transaction date, description, debit or credit direction, amount, and running balance across both supported multi-line HTML layouts. A balance-bearing continuation row without its own date inherits the preceding transaction date rather than disappearing.

Implement those compatibility cases through the existing `BankTransactionUtil` API. In particular, `processValue('03- JUL- 2017')` and `processValue('03-JUY-2017')` normalize to `03JUL2017`, which `dateFormatFromString` recognizes as `ddMMMyyyy`. Extend `headerDictionary()` so `balance_brought_forward` recognizes `OPENING BALANCE` and `junk_date` recognizes repeated headers such as `Txn. Date`. Keep `extractTransactionsFromHTMLHavingDescriptionAboveDate` and `extractTransactionsFromHTMLHavingDescriptionBelowDate` as the shared entry points.

Update the bank service adapters to send compatible statement layouts through the shared parser. Andhra's `WHERE INDIA BANKS` layout keeps its regex-specific path, Bank of Baroda's statement-criteria layout uses the description-above-date path, its other compatible layouts use the description-below-date path, and its distinct saving-account layout must continue using the existing dedicated parser. Consolidate common basic-detail extraction without regressing bank-specific account-holder rules.

Do not add real bank statements, customer data, cloud credentials, or production endpoints to the repository. The task must work against synthetic fixtures and preserve the behavior of unaffected formats.

Verify with:

    cd /app && sh /tests/test.sh
