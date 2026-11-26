# passthrough-shim

Flag module-level functions whose body is exactly `return f(...)`
where the call's args are the function's own parameters. These are
pass-through shims that add no behaviour and obscure the real callee.

Refinement (2026-11-01): only real forwarding is flagged. Every keyword
value must be a Name of one of the wrapper's parameters (a `**` keyword
or a computed value is not), no parameter may be passed twice across the
positional and keyword arguments (`table.get(name, name)` computes), and
a function with any decorator is skipped, since a decorator registers it
for something else (a fixture, a command, a route).
