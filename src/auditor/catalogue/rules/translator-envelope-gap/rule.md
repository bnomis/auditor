# translator-envelope-gap

Flag a body whose only error envelope is a translating decorator or
contextmanager whose except tuple is narrower than A2's locked set.

`filesystem-envelope-gap` and every other mechanical A2 check look for a
lexical `try/except` in the function. A `@translate_sqlite_errors`-style
decorator is invisible to that scan, so a function guarded only by one
reads as "no envelope at all" - and is then skipped, being neither
lexically guarded nor caught by the no-envelope checks. On one project
such sites in a query module survived several audit cycles: each
`json.loads` a sqlite column inside functions documenting
`Raises: StoreError` whose only envelope caught `sqlite3.Error`, so a
malformed column reached the CLI as a bare `json.JSONDecodeError`
traceback.

Signal:
  - Function F is decorated with, or contains a `with` block entering, a
    function defined in this package whose own `except` handler raises a
    `*Error` (see `handler_translates`). That handler's tuple is F's
    envelope.
  - F's body calls something that triggers a branch of A2's locked set:
    `json.load*` needs `json.JSONDecodeError`; `pd.read_*` needs
    `pandas.errors.ParserError`; `gzip.open` needs `gzip.BadGzipFile`;
    `read_text` needs `UnicodeDecodeError`; any filesystem primitive
    needs `OSError`.
  - The envelope's tuple satisfies none of the branch's exceptions.

Carve-outs, each of which must not fire:
  - A decorator catching bare `Exception` / `BaseException`, or a bare
    `except:`, satisfies every branch - exactly as a lexical one does.
  - A call already inside a lexical `try` in F. That envelope is the
    lexical checks' to judge, and reporting it here would double-count it.
  - A function with no resolvable translator at all. "No envelope" is
    `filesystem-op-without-envelope`'s question, not this one.

One finding per function, at its earliest triggering call, so a function
parsing several columns is one item of work rather than several.
