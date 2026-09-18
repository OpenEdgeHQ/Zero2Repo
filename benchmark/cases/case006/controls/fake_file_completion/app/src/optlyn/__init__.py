"""Negative control: collectable stub with fake File completion.

Exports every module-level name the hidden suite imports so collection
succeeds. Bash source prints a comment and does not call ``complete``.
"""

from __future__ import annotations

import os
import sys


class BadParameter(Exception):
    pass


class ParamType:
    name = "string"

    def convert(self, value, param=None, ctx=None):
        return value

    def shell_complete(self, ctx, param, incomplete):
        return [incomplete]


class File(ParamType):
    name = "file"

    def __init__(self, *args, **kwargs):
        pass


class Path(ParamType):
    name = "path"

    def __init__(self, file_okay=True, dir_okay=True, **kwargs):
        self.file_okay = file_okay
        self.dir_okay = dir_okay


class Choice(ParamType):
    def __init__(self, choices, **kwargs):
        self.choices = list(choices)

    def shell_complete(self, ctx, param, incomplete):
        return [item for item in self.choices if str(item).startswith(incomplete)]


class Context:
    def __init__(self, **kwargs):
        self.params = {}
        self.obj = None


class Group:
    def add_command(self, *args, **kwargs):
        return self


class CommandCollection(Group):
    pass


class DateTime(ParamType):
    name = "datetime"

    def __init__(self, *args, **kwargs):
        pass


class IntRange(ParamType):
    name = "integer range"

    def __init__(self, *args, **kwargs):
        pass


class FloatRange(ParamType):
    name = "float range"

    def __init__(self, *args, **kwargs):
        pass


class Tuple(ParamType):
    name = "tuple"

    def __init__(self, *args, **kwargs):
        pass


STRING = ParamType()
INT = ParamType()
INT.name = "integer"
FLOAT = ParamType()
FLOAT.name = "float"
BOOL = ParamType()
BOOL.name = "boolean"
UUID = ParamType()
UUID.name = "uuid"
UNPROCESSED = ParamType()
UNPROCESSED.name = "unprocessed"


def option(*_args, **_kwargs):
    def wrap(fn):
        return fn

    return wrap


def argument(*_args, **_kwargs):
    def wrap(fn):
        return fn

    return wrap


class _Command:
    def __init__(self, callback):
        self.callback = callback
        self.name = getattr(callback, "__name__", "cmd")

    def add_command(self, *args, **kwargs):
        return self

    def main(self, args=None, prog_name=None, standalone_mode=True, **kwargs):
        exe = prog_name or (sys.argv[0] if sys.argv else "optlyn")
        env_name = (
            f"_{os.path.basename(str(exe)).replace('-', '_').upper()}_COMPLETE"
        )
        instruction = os.environ.get(env_name, "")
        if instruction.endswith("_source"):
            # Non-empty so the F12 source assertion passes, but no
            # ``complete`` registration so the named test reaches
            # NO_COMPLETE_REGISTRATION.
            print("# fake-completion: prefix only")
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


def _identity(*args, **kwargs):
    if args:
        return args[0]
    return None


def _decorator(*_args, **_kwargs):
    def wrap(fn):
        return fn

    return wrap


echo = _identity
secho = _identity
style = _identity
unstyle = _identity
echo_via_pager = _identity
progressbar = _identity
pause = _identity
clear = _identity
getchar = _identity
get_app_dir = _identity
get_pager_file = _identity
format_filename = _identity
open_file = _identity
edit = _identity
launch = _identity
prompt = _identity
confirm = _identity
get_current_context = Context
pass_context = _decorator
pass_obj = _decorator
make_pass_decorator = lambda *_a, **_k: _decorator
version_option = _decorator
help_option = _decorator
confirmation_option = _decorator
password_option = _decorator
custom_version_option = _decorator
