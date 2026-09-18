"""Minimal CliRunner so F08/F14 collect."""


class Result:
    exit_code = 1
    output = ""
    stdout = ""
    stderr = ""
    exception = None
    return_value = None


class CliRunner:
    def invoke(self, *args, **kwargs):
        return Result()
