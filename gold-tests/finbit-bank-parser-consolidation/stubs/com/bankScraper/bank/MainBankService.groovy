package com.bankScraper.bank

class QuietLog {
    void debug(Object ignored) {}
    void error(Object ignored) {}
    void error(Object ignored, Throwable error) {}
}

class MainBankService {
    def log = new QuietLog()
}
