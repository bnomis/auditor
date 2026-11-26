# spec-api-signature-drift

Flag a `def` in a spec's API block whose signature no longer matches the source.

A spec states a function's contract in a fenced block under an `API` heading. When a change adds a parameter and the spec is not updated in the same commit, the two drift, and a reader cannot detect it without opening both files. Both halves are machine-readable, so this asks the question mechanically.

It is a project check: it reads the specs and the whole corpus, never the root it is handed, so the driver runs it once per sweep.

Signal:

- a `def` or `async def` line inside a fenced code block that follows an `## API` (or `### API`) heading and precedes the next heading;
- the same bare name resolves to exactly one module-level definition across the whole corpus (`auditor.api.corpus_definitions`);
- the ordered parameter lists differ (names, `*` placement and the presence of a default, never types).

Refinements (each has a test asserting it does not fire):

- **An ambiguous name does not fire.** If the corpus holds more than one module-level `def` with that name, the check cannot know which one the spec means.
- **A method in a spec's `class` block does not fire.** A `def` indented under a `class` line in the same fence is a method, and methods are not in the corpus definitions.
- **A name with no module-level definition does not fire.** A Protocol method and its implementations, and `__init__` everywhere, resolve to methods only.
- **An elided signature does not fire.** `def f(...)` and a block carrying `# ...` show a contract rather than a signature.
- **Types are not compared.** A spec's `settings: AppSettings` against a source's `settings: applib.settings.AppSettings` is the same parameter.
- **Prose does not fire.** Only fenced blocks under an API heading are read.
- **Audit reviews and task lists are not read.** They are dated records, and flagging them would falsify the record. A spec in a hidden directory (a worktree checkout) is not read either.

Raised as a request by an audit (shipped 2026-09-01) that found many instances by hand in a single pass, nearly all of them a parameter added by a fix whose commit did not touch the spec.
