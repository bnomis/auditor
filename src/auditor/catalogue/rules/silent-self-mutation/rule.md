# silent-self-mutation

Flag methods (other than __init__ / __post_init__ / setters / setX-named
methods / clear / reset / update / mutate / merge / replace / apply / patch /
override) that reassign `self.<attr>` where `<attr>`
was set from a constructor argument of the same name in __init__.

The pattern is: a method whose name signals a non-mutating operation
(a stage, a compute, a build, a load, a predict, a tokenize, a train,
an evaluate) silently mutates state the caller passed in. Downstream
stages consume the mutation through `self.<attr>` but a Python-API
caller holding a reference to the original sees their view drift.
