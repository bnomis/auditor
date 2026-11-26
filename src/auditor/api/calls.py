"""Call-name helpers that rules share."""

# The tokens that mark a callee as a sink: a function that writes, publishes or records.
SINK_TOKENS = ('dump', 'emit', 'flush', 'log', 'persist', 'publish', 'register', 'save', 'upload', 'write')

__all__ = ['SINK_TOKENS']
