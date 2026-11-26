# silent-broad-except

Flag a broad `except` handler that neither logs nor raises.

Signal: a handler for a bare `except:`, `Exception` or `BaseException`
(alone or in a tuple) whose body holds no `logger.`, `loguru.logger.` or
`logging.` text and no `raise` statement anywhere inside it. Carve-outs:
a handler naming only narrower exceptions; a file that does not parse.
