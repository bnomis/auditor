import auditor.api


def check(scope, src_root):
    auditor.api.emit(rule='fixture-hit', variant='one', path=None, line=None, evidence=src_root.name, accepted=False, accepted_reason=None)
