# legacy-formatting-percent

Flag `%s`/`%d`/`%r`-style C-printf formatting in Python string literals,
but do NOT flag strftime directives. Heuristic: if the literal contains
any strftime token (e.g. `%Y`, `%m`), treat it as a strftime call site.
