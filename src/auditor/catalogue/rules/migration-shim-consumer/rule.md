# migration-shim-consumer

Detect re-export shims (`X = canonical.X` style aliases) and flag
any consumer that imports via the shim instead of the canonical home.

Mechanical signal: a module-level assignment `X = pkg.mod.X` where the
LHS name equals the RHS attribute is a re-export shim for symbol X
whose canonical home is `pkg.mod`. Any importer that reads `X` via
the shim's path is using a deprecated migration shim.
