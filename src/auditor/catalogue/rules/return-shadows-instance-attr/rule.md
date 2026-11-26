# return-shadows-instance-attr

Flag class methods that return a value named identically to an
instance attribute (either alone or as part of a tuple). The
contract "caller must reassign self.X" is implicit and unenforced.

Signal:
  - Class C stores `self.X` in `__init__` from a same-named arg.
  - A method M on C (other than __init__/__post_init__) returns
    either `X` directly or a tuple that contains a local `patched_X`
    / `new_X` / `X` (i.e. a Name whose id is `X` or contains `X`).
  - The method's docstring or body mutates the local value away
    from `self.X`.

This is the `Pipeline.tokenize` pattern: returns `(tokenized,
patched_config)` where `patched_config` is a divergent copy of
`self.config`; callers must `self.config = patched_config` or the
instance silently drifts.
