# mixed-raise-types

Flag methods/functions that raise two or more different exception
types where the types do not share a clear inheritance relationship.
A common architecture smell: half the invariants raise PipelineError,
half raise stdlib RuntimeError - callers cannot establish a clean
catch envelope.
