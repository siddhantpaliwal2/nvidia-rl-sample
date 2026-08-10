package com.bankScraper.bank

class BankTransactionResponse {
    Date transactionDate
    Date valueDate
    String description
    def type
    Double amount
    BigDecimal balanceAfterTransaction
    String remark
}
