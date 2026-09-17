"""Negative control: recovery always succeeds."""

from __future__ import annotations

import hashlib


class HMACAlgorithm:
    def __init__(self, digest_method=hashlib.sha1):
        self.digest_method = digest_method


class NoneAlgorithm:
    pass


class Signer:
    def __init__(self, secret_key, **_kwargs):
        del secret_key

    def sign(self, value):
        payload = value if isinstance(value, bytes) else str(value).encode()
        return payload + b".AAAA"

    def unsign(self, token):
        raw = token if isinstance(token, bytes) else str(token).encode()
        return raw.rsplit(b".", 1)[0]

    def validate(self, token):
        del token
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
