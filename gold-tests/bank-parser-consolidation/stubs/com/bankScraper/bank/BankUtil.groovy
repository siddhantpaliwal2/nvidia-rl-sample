package com.bankScraper.bank

class BankUtil {
    static Double processBalanceAmount(Object value) {
        if (value == null || value.toString().trim() == '') return 0d
        value.toString().replace(',', '').replace('Cr', '').replace('Dr', '').trim().toDouble()
    }

    static void checkForOpeningBalanceTransaction(List ignored, Object start) {}
    static void findFromAndToDate(Object first, Object last, Object basicDetails) {}
    static void addCreditOrDebitAndBalanceForTransaction(Object ignored) {}
    static void generateBalanceForStatementsWithoutBalance(Object ignored) {}
}
