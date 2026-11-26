# empty-init-while-siblings-export

Flag any subpackage `__init__.py` that exports nothing while at
least one sibling subpackage exports a non-trivial public surface.
Sparse public surfaces force consumers to reach into private submodules.

Acceptance: this is a file-level finding, so the
accept-marker scan looks at every line in the file rather than just
the docstring line. A docstring-only ``__init__.py`` cannot host an
inline comment on the docstring opener; the marker has to land on a
separate comment-only line. Any line containing
``# auditme: accept <reason>`` accepts the file.
