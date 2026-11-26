# phase-section-doc-reference

Flag a docstring or comment in the source that names a numbered `Phase N` or `Section X.Y` spec location. Such cross-references rot when a spec is renumbered.

Signal:

- a line in a `.py` file under the root matches `\bPhase [1-9][a-z]?\b` or `\bSection [0-9]+\.[0-9]+\b`;
- the line is part of a docstring, or is a comment;
- the file carries no file-level `# auditme: accept phase-section <reason>` comment, which excuses a module that renders user-facing phase vocabulary wholesale;
- the hit is not accepted by an inline marker.

A reference in running code (a string value) is not a hit: the rule is about cross-references that rot, not about user-facing text.
