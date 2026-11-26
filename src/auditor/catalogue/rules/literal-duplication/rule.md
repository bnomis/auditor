# literal-duplication

Flag the same string-literal collection written in two or more places.

Refinement (2026-11-21): in a test file (a `tests` directory, `test_*.py`,
`*_test.py` or `conftest.py`) a one-member literal and a literal inside an
`assert` statement or a `pytest.param(...)` call are expectations, not
shared data, and are not counted. A multi-member literal in test set-up
still counts, and so does any literal in source.
