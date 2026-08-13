import com.bankScraper.bank.AndhraBankUtil
import com.bankScraper.bank.BankOfBarodaUtil
import com.bankScraper.bank.BankTransactionUtil
import com.bankScraper.bank.ProcessedBankStatementVO
import com.bankScraper.bank.pdf.AndhraBankPdfService
import com.bankScraper.bank.pdf.BankOfBarodaPdfService
import com.fintechlabs.pdf2table.PDF2Table
import groovy.json.JsonOutput

ExpandoMetaClass.enableGlobally()

def results = []
def check = { String name, Closure behavior ->
    try {
        behavior.call()
        results << [name: name, status: 'passed']
        println "PASS ${name}"
    } catch (Throwable error) {
        results << [name: name, status: 'failed']
        System.err.println("FAIL ${name}: ${error.class.simpleName}: ${error.message}")
    }
}

def parserState = {
    new ProcessedBankStatementVO(
        processBankStatementCO: [bankStatement: new File('/tmp/synthetic-statement.pdf'), password: ''],
        bankTransactionList: [],
        statementStatus: [statementParsedStatus: null, exceptionStackTrace: null],
        basicDetails: [fromDate: null],
    )
}

def transactionHtml = { String firstRow, String secondRow = '' ->
    """<table>
      <tr><td>Txn Date</td><td>Description</td><td>Debit</td><td>Credit</td><td>Balance</td></tr>
      ${firstRow}
      ${secondRow}
    </table>"""
}

def parseBelow = { String html ->
    PDF2Table.metaClass.'static'.fetchTransactionHTML = { File ignored, String password -> JsonOutput.toJson([html]) }
    def state = parserState.call()
    BankTransactionUtil.extractTransactionsFromHTMLHavingDescriptionBelowDate(state)
    state
}

def parseAbove = { String html ->
    PDF2Table.metaClass.'static'.fetchTransactionHTML = { File ignored, String password -> JsonOutput.toJson([html]) }
    def state = parserState.call()
    BankTransactionUtil.extractTransactionsFromHTMLHavingDescriptionAboveDate(state)
    state
}

check('Bank parser consolidation normalizes compact and OCR-corrupted month dates') {
    assert BankTransactionUtil.processValue('03- JUL- 2017') == '03JUL2017'
    assert BankTransactionUtil.processValue('03-JUY-2017') == '03JUL2017'
    assert BankTransactionUtil.dateFormatFromString('03JUL2017').toPattern() == 'ddMMMyyyy'
}

check('Bank parser consolidation recognizes opening balances and repeated transaction headers') {
    def headers = BankTransactionUtil.headerDictionary()
    assert 'OPENING BALANCE'.find(headers.balance_brought_forward)
    assert 'Txn. Date'.find(headers.junk_date)
}

check('Bank parser consolidation parses an irregular date through the description-below-date layout') {
    def html = transactionHtml.call(
        '<tr><td>03-JUY-2017</td><td>WIRE PAYMENT</td><td>125.00</td><td></td><td>875.00</td></tr>',
    )
    def state = parseBelow.call(html)
    assert state.bankTransactionList.size() == 1
    assert state.bankTransactionList[0].description.trim() == 'WIRE PAYMENT'
    assert state.bankTransactionList[0].amount == 125d
    assert state.bankTransactionList[0].type.toString() == 'DEBIT'
    assert state.bankTransactionList[0].balanceAfterTransaction == 875d
}

check('Bank parser consolidation retains balance-only continuation rows in the description-above-date layout') {
    def html = transactionHtml.call(
        '<tr><td>01/09/2017</td><td>SALARY</td><td></td><td>100.00</td><td>1000.00</td></tr>',
        '<tr><td></td><td>MONTHLY FEE</td><td>10.00</td><td></td><td>990.00</td></tr>',
    )
    def state = parseAbove.call(html)
    assert state.bankTransactionList.size() == 2
    assert state.bankTransactionList[1].transactionDate == state.bankTransactionList[0].transactionDate
    assert state.bankTransactionList[1].description == 'MONTHLY FEE'
    assert state.bankTransactionList[1].amount == 10d
    assert state.bankTransactionList[1].balanceAfterTransaction == 990d
}

check('Bank parser consolidation routes heterogeneous bank layouts through the correct shared parser') {
    def calls = []
    BankTransactionUtil.metaClass.'static'.extractTransactionsFromHTMLHavingDescriptionAboveDate = {
        ProcessedBankStatementVO ignored -> calls << 'shared-above'
    }
    BankTransactionUtil.metaClass.'static'.extractTransactionsFromHTMLHavingDescriptionBelowDate = {
        ProcessedBankStatementVO ignored -> calls << 'shared-below'
    }
    AndhraBankUtil.metaClass.'static'.extractTransactionsUsingRegex = {
        ProcessedBankStatementVO ignored -> calls << 'andhra-regex'
    }
    BankOfBarodaUtil.metaClass.'static'.extractTransactionsFromCurrentAccount = {
        ProcessedBankStatementVO ignored -> calls << 'baroda-legacy-current'
    }

    def andhra = File.createTempFile('andhra-synthetic-', '.txt')
    def barodaCriteria = File.createTempFile('baroda-criteria-', '.txt')
    def barodaDefault = File.createTempFile('baroda-default-', '.txt')
    try {
        andhra.text = 'WHERE INDIA BANKS'
        barodaCriteria.text = 'Statement Criteria Transactions in the date range SrN'
        barodaDefault.text = 'regular compatible statement'
        def status = [message: null, exceptionStackTrace: null, statementParsedStatus: null]
        new AndhraBankPdfService().parsePDFStatementForTransactions(
            new ProcessedBankStatementVO(processBankStatementCO: [textFile: andhra], statementStatus: status),
        )
        new BankOfBarodaPdfService().parsePDFStatementForTransactions(
            new ProcessedBankStatementVO(processBankStatementCO: [textFile: barodaCriteria], statementStatus: status),
        )
        new BankOfBarodaPdfService().parsePDFStatementForTransactions(
            new ProcessedBankStatementVO(processBankStatementCO: [textFile: barodaDefault], statementStatus: status),
        )
        assert calls == ['andhra-regex', 'shared-above', 'shared-below']
    } finally {
        andhra.delete()
        barodaCriteria.delete()
        barodaDefault.delete()
    }
}

check('Bank parser consolidation preserves standard numeric date parsing') {
    assert BankTransactionUtil.processValue('03-07-2017 10:30') == '03-07-2017'
    assert BankTransactionUtil.dateFormatFromString('03/07/2017').toPattern() == 'dd/MM/yyyy'
}

check('Bank parser consolidation preserves the dedicated Bank of Baroda saving-account route') {
    def calls = []
    BankOfBarodaUtil.metaClass.'static'.extractTransactionsFromSavingAccount = {
        ProcessedBankStatementVO ignored -> calls << 'baroda-saving'
    }
    def statement = File.createTempFile('baroda-saving-', '.txt')
    try {
        statement.text = 'Joint Holders PARTICULARS'
        new BankOfBarodaPdfService().parsePDFStatementForTransactions(
            new ProcessedBankStatementVO(
                processBankStatementCO: [textFile: statement],
                statementStatus: [message: null, exceptionStackTrace: null, statementParsedStatus: null],
            ),
        )
        assert calls == ['baroda-saving']
    } finally {
        statement.delete()
    }
}

new File('/tmp/finbit-unit.json').text = JsonOutput.prettyPrint(JsonOutput.toJson([tests: results]))
if (results.any { it.status != 'passed' }) System.exit(1)
