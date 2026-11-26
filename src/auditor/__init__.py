"""The auditme mechanical sweep.

`sweep.py` is the `auditor check` entry point and owns only argument parsing and the
run loop; everything else lives here.

    core.py       the five helpers nearly every check uses - emit, source
                  reading, path relativisation, and the accept-marker scan
    catalogue/    the default rule catalogue, a rules repository: one
                  directory per rule. The runner holds no rules itself; it
                  loads the repository `$AUDITOR_RULES_PATH` names

A check is a plain function `(scope, src_root) -> None` that emits zero or
more hits. It reports; it never decides. Acceptance is the accept marker's
job and triage is the reviewer's, which is why a check has no return value
and no severity.

Adding a check: add a rule directory (`rule.toml`, `check.py`, `tests/`) to
the rules repository. Rules run in name order, so renaming one reorders the
output and will read as a diff in the next audit.
"""
