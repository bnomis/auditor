# The audit checker

```shell
uv run --no-project python claude/skills/auditme/checks/audit.py .
```

The checker is the mechanical half of the `auditme` skill: a static sweep,
written against the standard library only, that parses each file and prints
one JSON object per hit. It reports; it never decides. Triage is the
reviewer's job, and acceptance is the accept marker's.

It needs Python 3.14 or later. The `ruff` and `ruff-version-drift` rules run
the project's `.venv/bin/ruff` when that is executable, else `ruff` from
`PATH`, and `lockfile-drift` runs `uv lock --check`.

## What it audits

Every path is relative to the project root passed as the first argument.

- **Packages under `src/<package>/`**: each package is audited in its own
  pass, so module names are built without a `src.` prefix. `src/` is
  optional.
- **Declared roots**: when `[tool.auditme]` in `pyproject.toml` declares
  `roots`, those are the swept roots, in place of the packages and extra roots
  below.
- **Scripts in `bin/`**: the default extra root, used when it exists and holds
  `.py` files. `--extra-root` replaces the default set.
- **A `.py` file directly in `src/`**: it belongs to no pass, so it is
  reported as a `src-loose-module` hit.
- **Markdown**: every `.md` file under the root is read for
  `spec-api-signature-drift`, except those in a hidden directory or in a
  `.git`, `.venv`, `node_modules`, `__pycache__`, `audit-reviews` or `tasks`
  directory.
- **Project files**: `pyproject.toml` with `uv.lock` and `.pre-commit-config.yaml`
  are read by the project-level checks (see
  [Project-level checks](#project-level-checks)); `AGENTS.md` is read only by
  per-root checks (the *gated* rules and the import rules).

No other directory is swept.

## Running it

### `audit.py`: the full report

```shell
uv run --no-project python claude/skills/auditme/checks/audit.py <project-root> [--package <pkg>] [--extra-root <dir> ...]
```

| Flag | Effect |
|---|---|
| `--package <pkg>` | Audit only `src/<pkg>/`. Drops the extra roots and the `src-loose-module` report too. For re-checking one package while verifying a fix; a normal audit passes neither flag. |
| `--extra-root <dir>` | Audit `<dir>` (relative to the root) as its own pass. Repeatable. Replaces the default set (`bin/`). A named root that does not exist is an error, not an empty pass. |

`audit.py` prints every hit, accepted or not, and exits 0 whatever it finds.
It exits 2 on a usage error from argparse (an unknown option or a missing value); when the root is not a directory; when `--package` is not a plain
directory name; when a named extra root is outside the root or is not a
directory; when the `--package` directory is missing; or when `[tool.auditme]`
in `pyproject.toml` is invalid. A project with no package and no extra root prints a note on stderr
and exits 0.

### `changed.py`: the gate

```shell
uv run --no-project python claude/skills/auditme/checks/changed.py           # changed files only
uv run --no-project python claude/skills/auditme/checks/changed.py --all     # every file
```

`changed.py [--all] [--base <ref>] [<repo-root>]` runs `audit.py` over the
whole tree, so cross-file rules see every file, then keeps the unaccepted hits
in scope. It exits 1 when any remain, or on any failure: an argument error, a
`--base` that is a flag, git that cannot run, a diff or `rev-parse` that fails,
or a sweep that cannot start, times out, exits non-zero, prints a line that is
not a JSON object, or reports a crashed check. It exits 0 otherwise. A sweep that cannot run is never skipped.

| Mode | Scope | Runs as |
|---|---|---|
| default | Files changed in `<base>...HEAD`, plus tracked files changed in the index or working tree against `HEAD` (an untracked file is in scope once staged). A hit is in scope when its `path`, or any of its `related` paths, is. | The `auditme-changed` pre-commit hook |
| `--all` | Every file | The `auditme-all` hook: the push gate and CI |

`--base` defaults to the first of `@{upstream}`, `origin/main` and `main` that
resolves. With none, or with no reportable file changed (a `.py` file, a `uv.lock`, or a `.md` file outside hidden directories and outside `audit-reviews` and `tasks`, among others),
it prints why and exits 0 without sweeping. `<repo-root>` defaults to the
working directory's git top level.

The same runs through pre-commit:

```shell
pre-commit run auditme-all --hook-stage manual --all-files
```

To let one commit or push through, `SKIP=auditme-changed git commit` or
`SKIP=auditme-all git push`.

## Reading the output

`audit.py` prints one JSON object per line, keys sorted:

```text
{"accepted": false, "accepted_reason": null, "evidence": "except Exception:", "line": 9, "path": "src/pkg/core.py", "rule": "silent-broad-except", "variant": "no logger and no raise in body"}
{"accepted": true, "accepted_reason": "best-effort read of an optional cache", "evidence": "except Exception:", "line": 17, "path": "src/pkg/core.py", "rule": "silent-broad-except", "variant": "no logger and no raise in body"}
{"accepted": false, "accepted_reason": null, "evidence": "def load(path, strict): | src/pkg/core.py:6", "line": 6, "path": "docs/spec.md", "related": ["src/pkg/core.py"], "rule": "spec-api-signature-drift", "variant": "load: spec says (path, strict), source says (path)"}
```

| Key | Meaning |
|---|---|
| `rule` | The rule id (see [The rules](#the-rules)) |
| `variant` | Which form of the rule fired, or a summary of this hit |
| `path` | Repository-relative path, or `null` for a hit with no file |
| `line` | 1-based line, or `null` |
| `evidence` | The source snippet or identifier that matched |
| `accepted` | `true` when an accept marker or, for `in-function-import` only, an `AGENTS.md` row covers the hit; an `AGENTS.md` row for `layering-violation` makes the check print no hit at all |
| `accepted_reason` | `null` for a hit that is not accepted; otherwise the marker's reason, `no reason given` for a marker with none, or `AGENTS.md accepted (<importer> -> <imported>)` for an `in-function-import` hit an `AGENTS.md` row covers |
| `related` | Only on a hit that compares files: the other files' paths, sorted, never the hit's own |

Identical hits are printed once, so a hit that several passes would each
report appears once.

`changed.py` prints only unaccepted hits in scope, sorted by path and line, as
`<path>:<line>  <rule>` with the variant indented beneath, then how to fix or
skip:

```text
src/pkg/core.py:9  silent-broad-except
    no logger and no raise in body

Fix each hit, or accept one with a comment on its line or the line above:
    # auditme: accept[<rule>] <reason>
To skip this check for one commit: SKIP=auditme-changed git commit
```

## Accepting a hit

Fix the hit, or accept it with a comment on the hit's line or the line above:

```python
def other(path):
    try:
        return open(path).read()
    # auditme: accept[silent-broad-except] best-effort read of an optional cache
    except Exception:
        return None
```

The marker matches `# auditme: accept[<rule>] <reason>` anywhere on the line,
so it can follow code or a `# noqa`. A few rules (`from-import`,
`except-interpolation`, `spec-api-signature-drift`) also take a marker on any
line of a statement that spans several lines.

- **Scope it to a rule.** `accept[<rule>]` answers only for that rule; a hit
  from another rule on the same line stays unaccepted. The unscoped form,
  `# auditme: accept <reason>`, answers for every rule on the line, including
  rules added after it was written, so write new markers scoped.
- **One marker per rule.** A line that two rules hit can carry two scoped
  markers, `# auditme: accept[rule-a] <reason>  # auditme: accept[rule-b] <reason>`;
  each reason ends where the next marker begins.
- **Give a reason.** It is copied into `accepted_reason` and is what a
  reviewer reads instead of re-arguing the hit.
- **Line-1 markers.** `src-loose-module` is reported at line 1, so its marker
  goes on line 1 of the file:
  `# auditme: accept[src-loose-module] <reason>`.
- **File-level rules.** `empty-init-while-siblings-export` is accepted by a
  marker on any line of the `__init__.py`. `phase-section-doc-reference`
  skips a whole file that carries a comment-only line matching
  `# auditme: accept ... phase-section ...` (unscoped, with `phase-section`
  in the reason).
- **Markdown.** A `spec-api-signature-drift` hit is accepted by the same
  comment inside the fenced block, on the `def` line, the line above it, or any
  line of the signature:

    ````markdown
    ```python
    # auditme: accept[spec-api-signature-drift] strict lands in the next change
    def other(path, strict):
        ...
    ```
    ````

- **`AGENTS.md` tables.** An `in-function-import` hit is accepted by a table
  row in the project's `AGENTS.md` pairing the importer and imported module in
  backticks, written without a `src.` prefix (`pkg.config.structures`). A
  `layering-violation` is accepted by a pair in the accepted-exceptions table
  of the `AGENTS.md` Package Layering section.

!!! note "Hits a marker cannot accept"
    `ruff` hits come from ruff and are silenced the ruff way (`# noqa: <code>`
    or the project's ruff config). `lockfile-drift`, `auditme-check-crash` and `unreadable-file`
    have no marker either: regenerate the lockfile, fix the checker, or make the file readable.

Nothing else counts as acceptance: not a prior review, a decision note, or a
belief that the pattern is intentional.

## The rules

Each rule's predicate, and every carve-out that keeps it from firing, is in
the docstring of its `check_*` function under
`claude/skills/auditme/checks/auditme/rules/`; the hits `audit.py` emits itself
(see Driver below) have no such docstring. Rules marked *gated* fire only
when the project's `AGENTS.md` declares the standard they enforce.

Which shared rule each checker rule enforces is listed under "Rules enforced
by a check" in the agents repository's rules reference
(<https://bnomis.github.io/agents/reference/rules/>).

### Driver

Emitted by `checks/audit.py` itself, not by a registered check.

| Rule id | Reports |
|---|---|
| `src-loose-module` | A `.py` file directly in `src/`, outside any package |
| `unreadable-file` | A file a check could not read (gone, denied or not UTF-8); `path` names it and `evidence` is always `cannot read <name>`, without the reason. The check skips it and reports its other hits. |
| `auditme-check-crash` | A check raised; `variant` names it and `evidence` the exception. `changed.py` fails on it. |

### `duplication.py`

| Rule id | Reports |
|---|---|
| `literal-duplication` | The same collection literal (tuple, list, set, frozenset) in several places |
| `paired-sibling-helpers` | Top-level functions with the same body in different files |
| `duplicate-side-effect-per-target` | Several methods of a class calling the same sink with the same `self` attribute |
| `redundant-sink-caller-plus-callee` | A function calling a sink, then a helper that calls the same sink with the same arguments |
| `duplicate-call-sequence` | Two functions in different classes or modules sharing a long ordered run of calls |
| `recompile-duplication` | A `re.compile(...)` constant whose name is also compiled in another file |

### `error_handling.py`

| Rule id | Reports |
|---|---|
| `silent-broad-except` | `except Exception` with no logger call and no raise |
| `broad-except-wrong-level` | A broad `except` logging at warning, error, info or debug instead of `logger.exception` |
| `except-interpolation` | A caught exception interpolated into an f-string or passed as a logger argument |
| `mixed-raise-types` | A function raising both stdlib and project exceptions with no shared base |
| `asymmetric-exception-translation` | A function with no error translation of its own whose every caller wraps it |
| `sibling-errors-no-common-base` | Error classes in one `errors.py` that do not share a parent |
| `cli-entry-missing-error-envelope` | A `run_*` function in `cli/*.py` with no top-level `try`/`except` |
| `try-wrapping-with-block-too-broad` | A `try: with X():` whose handler repeats work from the `with` body |
| `layer-has-domain-error-raises-stdlib` | A module raising a stdlib exception where its package defines domain errors |
| `inconsistent-error-translation` | Callers of one helper translating its error to different project errors |
| `filesystem-envelope-gap` | A `try` around a filesystem-touching third-party helper whose `except` omits `OSError` |
| `filesystem-op-without-envelope` | A public function writing to the filesystem with no `try`/`except` |
| `logger-exception-graceful-degradation` | A handler calling `logger.exception` then returning a constant default |
| `docstring-raises-mismatch` | A docstring `Raises:` naming a different exception from the one the body raises |
| `missing-raises-section` | A function raising a project error that reaches its caller (not one a handler around it catches without re-raising) whose docstring has no `Raises:` section |
| `bare-except-in-module-with-narrow-errors` | `except Exception` in a module that elsewhere catches a narrow `*_ERRORS` tuple |
| `failure-as-absence` | A clean-absence return (`None`, empty) reached from a caught exception or a non-200 response |
| `get-container-default-then-method-call` | `x = d.get(k, {})` later used as a method receiver: the default does not fire for an explicit null |
| `translator-envelope-gap` | A body whose only error envelope is a translating decorator or context manager with too narrow an `except` |
| `raises-section-drift` | A `Raises:` section naming an error that never reaches the caller, or omitting one that does (a callee error guarded only by optional arguments the call leaves unset does not count). Errors are followed through callees with no `Raises:` section and through `Class.method()` calls |

### `imports_and_surfaces.py`

| Rule id | Reports |
|---|---|
| `def-class-in-init` | A top-level `def` or `class` in an `__init__.py` |
| `in-function-import` | An import inside a function (variant: stdlib, first-party or third-party), outside `TYPE_CHECKING` and `ImportError` guards |
| `unused-submodule-import` | `import X.Y.Z` never referenced |
| `layering-violation` | A first-party import going up the `AGENTS.md` package layering (*gated*) |
| `passthrough-shim` | An undecorated module-level function whose body is only `return f(...)`, passing each of its own parameters once, by name or position |
| `empty-init-while-siblings-export` | A subpackage `__init__.py` exporting nothing while a sibling exports a substantial surface |
| `migration-shim-consumer` | An import through a re-export shim instead of the symbol's canonical module |
| `reexport-in-non-init` | `X = some.module.X` at module scope outside an `__init__.py` |
| `annotated-all-assignment` | `__all__: list[str] = [...]`, which a guard matching plain assignment skips |
| `as-import` | `import X as Y` or `from M import X as Y` (*gated*) |
| `from-import` | `from X import Y` outside an `__init__.py` |

### `project_hygiene.py`

| Rule id | Reports |
|---|---|
| `ruff` | A `ruff check` diagnostic (variant: the ruff code), a file `ruff format --check` would reformat (variant `ruff-format`, at the line ruff names), ruff missing, or ruff output that is not JSON (`ruff-check-parse-error`, `ruff-format-parse-error`) |
| `lockfile-drift` | `uv lock --check` failing: the lockfile is out of date, or could not be verified |
| `ruff-version-drift` | The ruff the audit runs differs from the `ruff-pre-commit` `rev`, or either version cannot be read |
| `phase-section-doc-reference` | A docstring or comment citing `Phase N` or `Section X.Y` of a spec |
| `spec-api-signature-drift` | A `def` in a fenced block under a spec's `API` heading whose parameters differ from the source |

### `state_and_effects.py`

| Rule id | Reports |
|---|---|
| `constructor-disk-io` | Disk I/O inside `__init__` |
| `silent-self-mutation` | A method other than a setter, `clear`, `reset`, `update`, `mutate`, `merge`, `replace`, `apply`, `patch` or `override` reassigning an attribute set from a constructor argument |
| `return-shadows-instance-attr` | A method returning a value named like an instance attribute, leaving the caller to reassign it |
| `parameter-mutation-in-pure-function` | A function named or documented as a check that mutates a parameter |
| `pure-name-has-side-effect` | A function with a query-like name calling a write or I/O side effect |
| `mutable-store-without-copy` | `__init__` storing a dict or list parameter on `self` without a copy |
| `assert-never-missing` | An `if`/`elif` chain on string equality ending without `else: typing.assert_never(...)` |
| `build-name-has-side-effect` | A `build_*` or `compute_*` function calling subprocess, the clock, `uuid`, `random` or a filesystem write |
| `mutable-module-level-exported` | A mutable module-level container read by name from another module |
| `mutable-members-in-immutable-wrapper` | An externally read container in a shallow immutable wrapper that still holds mutable members |
| `callback-hotpath-io` | A `Trainer` callback method doing filesystem I/O on every event |
| `dataclass-optional-always-set` | A dataclass field typed as optional, defaulting to `None`, that `__post_init__` always sets |
| `dead-local-init` | A local initialised at the top of a function and overwritten on every path before use |
| `subprocess-without-memoisation` | A function with a request-invariant name calling `subprocess` without a cache decorator |

### `style_and_naming.py`

The rules from `wildcard-imports` to `leading-underscore-attribute-access`,
`legacy-formatting-percent` aside, are regex matches on each non-comment line,
except the form of `leading-underscore-def-class` that finds a `def` or `class`
nested in a function, which comes from an AST check.

| Rule id | Reports |
|---|---|
| `wildcard-imports` | `from X import *` |
| `future-annotations` | `from __future__` |
| `aliased-imports` | `import X as Y`, at any indentation |
| `legacy-typing` | `Union[`, `Optional[`, `List[`, `Dict[`, `Tuple[`, `Set[`, `FrozenSet[` or `Type[` |
| `legacy-formatting-format` | `.format()` called on a string literal |
| `legacy-formatting-percent` | `%`-style formatting in a string literal, strftime directives excepted |
| `stdlib-logging` | An import of the stdlib `logging` module |
| `relative-import-nonpackage` | A relative import outside an `__init__.py` |
| `leading-underscore-def-class` | A `def` or `class` named `_x`, at module level or nested in a function |
| `leading-underscore-const-upper` | A module-level `_NAME = ...` |
| `leading-underscore-const-lower` | A module-level `_name = ...` |
| `leading-underscore-self` | `self._attr` |
| `leading-underscore-attribute-access` | `obj._attr`, in code or a docstring, except public stdlib names such as `os._exit` |
| `leading-underscore-binding` | A parameter or bound name with a leading underscore |
| `underscore-unpack-target-read` | A `_x` tuple-unpack target that is read afterwards |
| `underscore-forloop-target-read` | A `for _x in ...` target read inside the loop |
| `non-alphabetical-literal` | A collection of string members not in alphabetical order (`__all__` may instead follow ruff's RUF022 order) |
| `non-alphabetical-dict-keys` | A module-level dict with string keys not in alphabetical order |
| `bare-parametric-annotation` | `dict`, `list`, `tuple`, `set` or `frozenset` in an annotation without type parameters |
| `bare-nonbuiltin-generic-annotation` | A parameterisable non-builtin class (`collections.deque`, `queue.Queue`, ...) annotated without its parameter |
| `typing-deprecated-alias` | A `typing` alias deprecated by PEP 585, such as `typing.Sequence` |
| `duplicated-word` | A word repeated in a comment or string ("the the") |

### Project-level checks

A project-level check asks about the project, not a package, and runs once
(`PROJECT_CHECKS` in `registry.py`), whatever the number of passes:

- `ruff-version-drift` reads `.pre-commit-config.yaml` and is anchored at the
  `ruff-pre-commit` `rev:` line, where its marker goes. It is silent with no
  config or no `ruff-pre-commit` repo; a `rev` that names no version, and a
  ruff that cannot run, are hits.
- `lockfile-drift` runs only when both `pyproject.toml` and `uv.lock` exist,
  and reports a `uv` that cannot run as a hit.
- `spec-api-signature-drift` reads every Markdown file in scope against the
  whole corpus, so a per-root pass would repeat it. It fires only when the
  name resolves to exactly one module-level definition.

Every other check runs once per pass, over that pass's root. Among them,
`layering-violation`, `as-import` and `in-function-import` read `AGENTS.md`
for their gate or their acceptance tables, and `ruff` runs over the pass's
root. The driver prints identical hits once.

## The pinned version and upgrades

Projects pin the `auditme-changed` and `auditme-all` hooks to a revision of
this repository, so a new rule never fails a build until the project chooses
to upgrade. Upgrading can surface hits in code that passed before; fix or
accept them in the same commit as the upgrade. The commands are in
[Upgrading the checker](../setup.md#upgrading-the-checker), and installing and
adopting the hooks is covered in [Setting up the shared guards](../setup.md).

## Further reading

`claude/skills/auditme/SKILL.md` covers the rest of the skill: the
interpretive review that follows the sweep, the review and summary templates,
the convergence rules, and how to add or narrow a check.
