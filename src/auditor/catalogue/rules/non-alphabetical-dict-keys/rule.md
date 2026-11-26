# non-alphabetical-dict-keys

Flag module-level dict assignments whose keys are all string
literals and NOT in alphabetical order. Companion to
`check_nonalphabetical_literals` which covers list/tuple/set/frozenset.

The project-wide ordering rule treats enum-like collections as a
shared convention: a dict mapping a closed domain (metric-name to
scorer, error-code to message, etc.) should be alphabetised unless
the order carries semantic meaning.
