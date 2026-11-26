# A17 brief

**Brief version:** 6

You are a reviewer for one batch of a listed audit question. Judge each
candidate in the batch on its own and report one verdict per candidate.

## Security

Never list environment variables (`env`, `printenv`, `set`) or print an env
file. To test that a variable is set, use `[ -n "${VAR:-}" ]` and print only
yes or no.

## The question

- **A17. Public-surface drift.** For every `__init__.py` with `__all__`: is every symbol in `__all__` used outside the package? For every empty `__init__.py`: do consumers reach into private submodules? Flag bypasses of the canonical owning module. A submodule with a module-level `__all__` is judged the same way as an `__init__.py` with one: is every symbol in its `__all__` used outside the module?

## Input

The batch file holds one JSON object per line, one per candidate. Each has
`id` (the `__init__.py`'s or submodule's repo-relative path), `path`, `start` and `end`
(the file's lines), and a `payload` with:

- `all`: the names in the `__all__`, empty when the `__init__.py` has none (a submodule is listed only when it has one);
- `consumers`: for each name in `all`, every read from outside the
  package's directory (for a submodule, outside the submodule itself) and outside the test tree, as `path: line text`. It
  includes a read of the name from one of the package's submodules, and a
  `[project.scripts]` or `[project.entry-points]` target of `pyproject.toml`;
- `reach_ins`: present for an empty `__init__.py`; each outside read of a
  name from one of the package's submodules, as `path: line text`.

Read the `__init__.py`, and the consumer's file when the line does not decide
the verdict.

A line may also have `earlier`, the verdict this candidate last had
(`findings`, `reason`, `brief_version`, `judged`). Judge the candidate on its
own, then compare: if your verdict differs from `earlier`, say in `reason`
what changed your judgement.

## Thresholds

- A name in `all` with no consumer is a hit unless a dynamic use reads it: a
  literal `getattr`, `importlib.import_module`, or an entry point. Search
  for such a use before reporting the name.
- A consumer reading a name from a submodule when the `__init__.py` exports
  it is a bypass of the package surface, and a hit.
- For an empty `__init__.py`, a reach-in to a submodule the project marks
  private (named in no `__all__` of its package where the package has one, a
  leading underscore only where it has none) is a bypass, and a hit. A
  reach-in to any other submodule is the owning module and not a hit.
- A read from the test tree is not a consumer: a name only tests read is a
  finding, and the listed `consumers` already leave tests out.
- A read, from outside a package, of a submodule that the package's non-empty
  `__all__` leaves out bypasses the canonical owning module. Report it on
  that package's own `__init__.py` candidate, naming the reader and the
  submodule.
- A project's own written exception (an import-cycle carve-out, scripts
  treated as whitebox tooling) does not settle a read of a submodule that
  `__all__` leaves out: only an inline marker or an AGENTS.md table row
  accepts anything. Report the read; the operator dismisses it with the
  exception as the reason.

A case this brief does not settle is not a finding: judge it not flagged,
name the candidate and the case in your reply, and judge the rest as the brief
says. Every reviewer gives an unsettled case the same verdict, so it does not
depend on the batch; the operator settles a reported case when it should count.

## Output

Write one JSON line per candidate to the result file you are given, with
exactly these keys:

- `id`: the candidate's `id`;
- `findings`: `{"surface": ["what is wrong and the fix"]}` when it is a hit,
  or `{"surface": []}` when it is not;
- `reason`: one sentence on why, naming the name or the consumer that
  decides it.

Every candidate in the batch gets exactly one line.
