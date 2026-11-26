# layering-violation

Walk every import; if it is a first-party import and goes upward
in the layering chain, flag unless the (importer, imported) pair is
in AGENTS.md's accepted-exceptions table or the line carries an
`# auditme: accept` marker.
