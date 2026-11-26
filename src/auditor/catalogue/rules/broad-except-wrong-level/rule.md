# broad-except-wrong-level

Flag `except (Exception|BaseException):` blocks whose body calls
logger.warning / logger.error / logger.debug / logger.info instead of
logger.exception. Distinct from `silent-broad-except`, which only
catches blocks with NO logger call at all.

A broad handler that logs and returns a default is caught here at
`warning` and by `logger-exception-graceful-degradation` at `exception`.
SKILL.md's "Conflicts with no winner" rules on it: remove or narrow the
handler rather than change its level.
