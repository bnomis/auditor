# paired-sibling-helpers

Flag module-level functions in two or more files whose bodies are identical.

Signal: the unparsed body, leaving out docstring and bare-constant
statements, is the same text in functions of at least two different files.
Carve-outs: a body shorter than 40 characters is skipped, as is a group
whose functions all sit in one file. Each member of a group is one hit,
carrying the other files in `related`.
