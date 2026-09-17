"""Negative control: product opens a socket during import."""

from __future__ import annotations

import socket

_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


class Connection:
    def __init__(self, *args, **kwargs):
        del args, kwargs
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
