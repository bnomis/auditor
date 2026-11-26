# try-wrapping-with-block-too-broad

Flag `try: with X(): body...` patterns where the except handler
re-invokes work that was inside the `with` body, assuming the
exception came from `__enter__`.

Signal:
  - An `ast.Try` node whose body starts with an `ast.With` block.
  - The `with` body contains one or more call statements.
  - The `except` handler body itself contains at least one call
    whose callee name matches a callee inside the `with` body.
  - The handler's intent (per comments/log messages) is startup
    failure - but the catch will also fire for any exception raised
    inside the `with` body.

The `run_batch` double-run: `try: with open_batch_run(): run_pipeline_and_finalise(...)`
catches `RegistryError`, and the handler calls `run_pipeline_and_finalise(...)`
again. If `RegistryError` escapes from the `with` body (not startup),
the pipeline runs twice.
