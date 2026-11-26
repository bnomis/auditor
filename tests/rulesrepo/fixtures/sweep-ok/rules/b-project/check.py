import auditor.api


def check(scope, src_root):
    auditor.api.emit(rule='fixture-project', variant='once', path=None, line=None, evidence=scope.name, accepted=False, accepted_reason=None)
