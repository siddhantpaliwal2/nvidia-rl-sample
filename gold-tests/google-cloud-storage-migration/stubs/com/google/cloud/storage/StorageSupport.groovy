package com.google.cloud.storage

class Acl {
    enum Role { READER }

    static class User {
        static User ofAllUsers() { new User() }
    }

    static Acl of(User ignored, Role role) { new Acl() }
}

class BlobId {
    String bucket
    String name

    static BlobId of(String bucket, String name) {
        new BlobId(bucket: bucket, name: name)
    }
}

class BlobInfo {
    BlobId blobId
    List acl = []

    static Builder newBuilder(BlobId blobId) { new Builder(blobId: blobId) }

    static class Builder {
        BlobId blobId
        List acl = []

        Builder setAcl(List acl) {
            this.acl = acl
            this
        }

        BlobInfo build() { new BlobInfo(blobId: blobId, acl: acl) }
    }
}

class Blob {
    BlobInfo info
    byte[] content

    byte[] getContent() { content }
}

class Bucket {}
class BucketInfo {}

class Storage {
    Map<String, byte[]> objects = [:]
    Map<String, byte[]> seededByName = [:]
    BlobInfo lastBlobInfo

    Blob create(BlobInfo info, InputStream input) {
        create(info, input.bytes)
    }

    Blob create(BlobInfo info, byte[] bytes) {
        lastBlobInfo = info
        objects["${info.blobId.bucket}/${info.blobId.name}"] = bytes
        new Blob(info: info, content: bytes)
    }

    byte[] readAllBytes(BlobId id) {
        objects["${id.bucket}/${id.name}"] ?: seededByName[id.name]
    }

    Blob get(BlobId id) {
        byte[] bytes = readAllBytes(id)
        bytes == null ? null : new Blob(info: new BlobInfo(blobId: id), content: bytes)
    }

    void seed(String name, byte[] bytes) { seededByName[name] = bytes }
}

class StorageOptions {
    static Storage service = new Storage()

    static Builder newBuilder() { new Builder() }

    static class Builder {
        Builder setCredentials(Object ignored) { this }
        Builder setProjectId(String ignored) { this }
        StorageOptions build() { new StorageOptions() }
    }

    Storage getService() { service }
}
