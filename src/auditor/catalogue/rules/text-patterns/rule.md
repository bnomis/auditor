# text-patterns

Flag source lines that match a text pattern.

Refinement (2026-11-21): the rules in `CODE_ONLY_RULES` read each line with
its non-docstring string literals blanked, so fixture source or a regex
held in a plain string is not read as code. A docstring is still read.
