import com.bankScraper.Enums
import com.bankScraper.HelperMethod
import com.bankScraper.bank.Document
import com.google.cloud.storage.Storage
import com.google.cloud.storage.StorageOptions
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

def resetStorage = {
    StorageOptions.service = new Storage()
    StorageOptions.service
}

check('Google storage migration adds GOOGLE target and defaults new documents to it') {
    def google = Enums.StaticFileStorageTarget.valueOf('GOOGLE')
    assert new Document().staticFileStorageTarget == google
}

check('Google storage migration uploads bytes through the configured storage client') {
    def storage = resetStorage.call()
    def source = File.createTempFile('synthetic-cloud-upload-', '.txt')
    try {
        source.bytes = 'synthetic upload payload'.bytes
        assert HelperMethod.uploadObjectToGoogleCloudStorage(source, 'synthetic/upload.txt')
        assert storage.objects.size() == 1
        assert storage.objects.values().first() == source.bytes
        assert storage.lastBlobInfo?.blobId?.bucket
        assert storage.lastBlobInfo?.blobId?.name == 'synthetic/upload.txt'
    } finally {
        source.delete()
    }
}

check('Google storage migration downloads bytes through the configured storage client') {
    def storage = resetStorage.call()
    storage.seed('synthetic/download.txt', 'synthetic download payload'.bytes)
    def stream = HelperMethod.downloadObjectFromGoogleCloudStorage('synthetic/download.txt')
    assert stream?.bytes == 'synthetic download payload'.bytes
}

check('Google storage migration routes persisted GOOGLE documents to cloud storage') {
    def storage = resetStorage.call()
    storage.seed('synthetic/routed.txt', 'routed cloud payload'.bytes)
    def document = new Document(
        path: 'synthetic/routed.txt',
        staticFileStorageTarget: Enums.StaticFileStorageTarget.valueOf('GOOGLE'),
    )
    assert HelperMethod.downloadObjectFromLocalOrS3OrAzure(document).bytes == 'routed cloud payload'.bytes
}

check('Google storage migration leaves blank cloud paths inert') {
    def source = File.createTempFile('synthetic-cloud-blank-', '.txt')
    try {
        source.text = 'ignored'
        assert HelperMethod.uploadObjectToGoogleCloudStorage(source, '') == false
        assert HelperMethod.downloadObjectFromGoogleCloudStorage(null) == null
    } finally {
        source.delete()
    }
}

check('Google storage migration preserves local file download precedence') {
    def source = File.createTempFile('synthetic-local-download-', '.txt')
    try {
        source.bytes = 'local payload'.bytes
        def document = new Document(path: source.path)
        assert HelperMethod.downloadObjectFromLocalOrS3OrAzure(document).bytes == 'local payload'.bytes
    } finally {
        source.delete()
    }
}

check('Google storage migration preserves Azure target routing') {
    HelperMethod.metaClass.'static'.downloadObjectFromAzure = { String ignored ->
        new ByteArrayInputStream('azure payload'.bytes)
    }
    def document = new Document(
        path: '/tmp/synthetic-missing-azure-object',
        staticFileStorageTarget: Enums.StaticFileStorageTarget.AZURE,
    )
    assert HelperMethod.downloadObjectFromLocalOrS3OrAzure(document).bytes == 'azure payload'.bytes
}

new File('/tmp/finbit-cloud-unit.json').text = JsonOutput.prettyPrint(JsonOutput.toJson([tests: results]))
if (results.any { it.status != 'passed' }) System.exit(1)
