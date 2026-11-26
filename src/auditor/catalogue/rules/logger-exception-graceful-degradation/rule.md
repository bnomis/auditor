# logger-exception-graceful-degradation

Flag `except` handlers that call `logger.exception(...)` and then
`return <constant>` without raising. `logger.exception` is reserved
for unexpected failures; a handler that logs-then-returns-default is
a graceful-degradation path and should use `logger.warning` /
`logger.debug` instead, so log severity matches the handling
intent.

Signal:
  - An `ast.ExceptHandler` whose body contains a `logger.exception(...)`
    call AND contains no `ast.Raise`.
  - EITHER the handler body ends with `return <Constant>` OR the
    enclosing function body ends with `return <Constant>` (so the
    handler falls through to the graceful-degradation default).
  - The enclosing function's return annotation is NOT `int`. CLI entry
    points return `int` exit codes and `logger.exception + return 2`
    is the canonical CLI error-contract, not graceful degradation.

For a broad `except Exception` handler, the `logger.warning` this
suggests fires `broad-except-wrong-level` instead. SKILL.md's "Conflicts
with no winner" rules on it: remove the handler, or narrow it to the
expected exception and then use `logger.warning`.
