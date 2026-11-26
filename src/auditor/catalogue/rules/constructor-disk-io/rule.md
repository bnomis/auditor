# constructor-disk-io

Flag disk I/O operations inside `__init__` methods. Constructors
should accept already-loaded data, not perform I/O on demand.
