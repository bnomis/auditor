"""Call-name helpers that rules share."""

import auditor.surface

# The tokens that mark a callee as a sink: a function that writes, publishes or records.
SINK_TOKENS = ('dump', 'emit', 'flush', 'log', 'persist', 'publish', 'register', 'save', 'upload', 'write')

# The site finders live in the runner, where the Phase B A17 lister reads them too.
empty_init_sites = auditor.surface.empty_init_sites  # auditme: accept[reexport-in-non-init] the API publishes the runner's site finder under this name
migration_shim_sites = auditor.surface.migration_shim_sites  # auditme: accept[reexport-in-non-init] the API publishes the runner's site finder under this name

__all__ = ['SINK_TOKENS', 'empty_init_sites', 'migration_shim_sites']
