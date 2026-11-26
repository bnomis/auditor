"""The auditme mechanical sweep.

`sweep.py` is the `auditor check` entry point and owns only argument parsing and the
run loop; everything else lives here.

    core.py       the five helpers nearly every check uses - emit, source
                  reading, path relativisation, and the accept-marker scan
    registry.py   CHECKS, the tuple the sweep iterates. Its order is the
                  emission order, and therefore part of the output
    rules/        one module per family of defect

A check is a plain function `(scope, src_root) -> None` that emits zero or
more hits. It reports; it never decides. Acceptance is the accept marker's
job and triage is the reviewer's, which is why a check has no return value
and no severity.

Adding a check: write it in the rules module for its family, alongside any
helper only it uses, and add it to CHECKS. Where it goes in that tuple is a
free choice, but changing an existing entry's position reorders the output
and will read as a diff in the next audit.
"""
