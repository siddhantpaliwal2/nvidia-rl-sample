package com.bankScraper.bank

class ProcessBankStatementCO {
    def client
    def bank
    def contentType
    def bankStatement
    def fileName
    def password
}

class FailedStatementVO {
    def processBankStatementCO
    def fileName
}
