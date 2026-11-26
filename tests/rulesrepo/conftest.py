import sys
import typing

import pytest

import auditor.core
import auditor.rulesrepo

if typing.TYPE_CHECKING:
    import collections.abc


@pytest.fixture(autouse=True)
def isolate_state() -> collections.abc.Iterator[None]:
    auditor.core.clear_source_cache()
    yield
    for name in [name for name in sys.modules if name.startswith(auditor.rulesrepo.MODULE_PREFIX)]:
        del sys.modules[name]


collect_ignore_glob = ['fixtures/*']
