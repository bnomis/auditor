import auditor.api


def check(scope, src_root):
    auditor.api.emit(rule='fixture-tested', variant='per-root', path=None, line=None, evidence=None, accepted=False, accepted_reason=None)
