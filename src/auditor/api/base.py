"""The version of the helper API that rule code may import, and the error a Phase B helper raises."""

API_VERSION = (1, 0)


class PhaseBError(Exception):
    """A Phase B question, ledger, plan or write that cannot be used."""


__all__ = ['PhaseBError']
