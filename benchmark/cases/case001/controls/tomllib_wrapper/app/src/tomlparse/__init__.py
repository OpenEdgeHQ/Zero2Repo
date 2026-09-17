"""Negative control: wrap the standard-library TOML parser."""

from __future__ import annotations

import tomllib


class TOMLDecodeError(ValueError):
    pass


def loads(document, parse_float=None):
    try:
        return tomllib.loads(document, parse_float=parse_float) if parse_float else tomllib.loads(document)
    except tomllib.TOMLDecodeError as exc:
        raise TOMLDecodeError(str(exc)) from exc


def load(fp, parse_float=None):
    try:
        return tomllib.load(fp, parse_float=parse_float) if parse_float else tomllib.load(fp)
    except tomllib.TOMLDecodeError as exc:
        raise TOMLDecodeError(str(exc)) from exc
