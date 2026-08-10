package com.google.auth.oauth2

class ServiceAccountCredentials extends GoogleCredentials {
    static ServiceAccountCredentials fromStream(InputStream ignored) {
        new ServiceAccountCredentials()
    }
}
