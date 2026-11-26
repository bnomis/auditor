# duplicate-call-sequence

Flag two functions (across different classes or modules) that
share a long subsequence of call-name tokens in the same order.

Signal:
  - For every FunctionDef / AsyncFunctionDef, extract the ordered
    sequence of callee short-names from calls with >=1 argument and
    whose callee is dotted (skips stdlib / builtin 1-word calls).
  - Skip very short sequences (< 5 calls) to avoid false positives.
  - Normalise: drop sequential duplicates (so `logger.info` stutter
    does not dominate the signature).
  - Group functions by the longest-common-subsequence key, which
    is the ordered tuple of distinct callee short-names appearing
    in each function.
  - If two functions share a LCS-key of length >= 5, emit.
