package org.codehaus.groovy.grails.commons

class ApplicationHolder {
    static def application = [
        parentContext: [getResource: { String ignored -> [inputStream: new ByteArrayInputStream('{}'.bytes)] }],
        config: [grails: [serverURL: 'http://example.invalid']],
    ]
}
