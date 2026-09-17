"""Negative control: concat-of-hashes instead of HMAC."""

from __future__ import annotations

import base64
import hashlib


class HMACAlgorithm:
    def __init__(self, digest_method=hashlib.sha1):
        self.digest_method = digest_method


class NoneAlgorithm:
    pass


class Signer:
    def __init__(self, secret_key, **_kwargs):
        if isinstance(secret_key, (list, tuple)):
            secret_key = secret_key[-1]
        self.secret = secret_key if isinstance(secret_key, bytes) else str(secret_key).encode()

    def sign(self, value):
        payload = value if isinstance(value, bytes) else str(value).encode()
        digest = hashlib.sha1(self.secret).digest() + hashlib.sha1(payload).digest()
        return payload + b"." + base64.urlsafe_b64encode(digest).rstrip(b"=")

    def unsign(self, token):
        raw = token if isinstance(token, bytes) else str(token).encode()
        return raw.rsplit(b".", 1)[0]

    def validate(self, token):
        return True


class TimestampSigner(Signer):
    pass


class Serializer:
    def __init__(self, secret_key, **kwargs):
        self.signer = Signer(secret_key, **kwargs)

    def dumps(self, obj):
        import json

        return self.signer.sign(json.dumps(obj)).decode()

    def loads(self, token):
        import json

        return json.loads(self.signer.unsign(token))


class TimedSerializer(Serializer):
    pass


class URLSafeSerializer(Serializer):
    pass


class URLSafeTimedSerializer(Serializer):
    pass
