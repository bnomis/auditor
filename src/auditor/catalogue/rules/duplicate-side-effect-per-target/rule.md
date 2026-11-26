# duplicate-side-effect-per-target

Flag when two or more methods on the same class call the same
sink function with an argument pointing to the same attribute target.

Signal:
  - Class C defines methods M1, M2 (M1 != M2, both non-private,
    both non-dunder, neither named like a pure setter).
  - M1 and M2 each call F(<args>) where F is a module-level function
    in the project.
  - At least one argument to F is `self.<attr>` and is identical
    across the call sites.

Example: `Pipeline.tokenize` and `Pipeline.train` both call
`pkg.config.persistence.flush_resolved_config(..., self.run_dir)`.
Calling from multiple stages silently re-flushes the same target and
can overwrite a patched snapshot if stages write different config
versions.
