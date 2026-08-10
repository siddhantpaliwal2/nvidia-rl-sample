package com.bankScraper

class HelperMethod {
    static Double getSanitizeDouble(Object value) {
        value == null ? 0d : value.toString().replace(',', '').trim().toDouble()
    }

    static Double roundTo2Places(Object value) {
        Math.round((value as Double) * 100d) / 100d
    }
}
