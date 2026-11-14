"""Compiler-specific errors."""


class BuildError(Exception):
    pass


class BuildCancelada(Exception):
    pass
