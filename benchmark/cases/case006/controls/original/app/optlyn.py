"""Negative control: completion prints the incomplete token only."""

from __future__ import annotations

import os
import sys


class ParamType:
    name = "string"

    def convert(self, value, param=None, ctx=None):
        return value

    def shell_complete(self, ctx, param, incomplete):
        return [incomplete]


class File(ParamType):
    name = "file"


class Path(ParamType):
    name = "path"

    def __init__(self, file_okay=True, dir_okay=True):
        self.file_okay = file_okay
        self.dir_okay = dir_okay


class Choice(ParamType):
    def __init__(self, choices):
        self.choices = list(choices)

    def shell_complete(self, ctx, param, incomplete):
        return [item for item in self.choices if str(item).startswith(incomplete)]


STRING = ParamType()
INT = ParamType()


def option(*_args, **_kwargs):
    def wrap(fn):
        return fn

    return wrap


def argument(*_args, **_kwargs):
    def wrap(fn):
        return fn

    return wrap


class Group:
    """Minimal group type so F12 can collect; completion remains fake."""


class _Command:
    def __init__(self, callback):
        self.callback = callback

    def main(self, args=None):
        env_name = f"_{os.path.basename(sys.argv[0]).replace('-', '_').upper()}_COMPLETE"
        instruction = os.environ.get(env_name, "")
        if instruction.endswith("_source"):
            print("echo fake-completion")
            return 0
        if instruction.endswith("_complete"):
            words = os.environ.get("COMP_WORDS", "").split()
            print(words[-1] if words else "")
            return 0
        if self.callback:
            self.callback()
        return 0


def command(**_kwargs):
    def wrap(fn):
        return _Command(fn)

    return wrap


def group(**_kwargs):
    return command()
