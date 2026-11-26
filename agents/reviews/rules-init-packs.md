# Rules init: pack membership review

**Spec:** `agents/specs/rules-init/spec.md`
**Task list:** `agents/tasks/rules-init/tasks-1.md`, Task 1
**Created:** 2026-11-26
**Review page:** not published - the session that wrote this document had no
tool for publishing an interactive page (see Automatic checks)

## What is being reviewed and how

`auditor rules init` lets a user choose packs, a pack being a named group of
catalogue rules on one topic. The spec proposes eleven packs and leaves the
membership of each rule to this review. Below, every rule in
`src/auditor/catalogue/rules/` has a recommended pack and a one-line reason.
For each item, approve the recommendation or name a different pack from the
spec's list: `error-handling`, `imports`, `module-surfaces`,
`state-and-effects`, `duplication`, `style-and-naming`, `project-hygiene`,
`testing`, `documentation`, `security`, `performance`. The work stops until
every item has an answer; Task 2 then writes `packs.toml` from the Answers
section.

The rule the recommendations follow: a rule goes to the pack of the topic its
`rule.md` names first, and a standard goes with the checks that enforce it.
Where a rule names two topics, its first-named one wins.

## Automatic checks

- Every rule directory has exactly one recommendation, and every
  recommendation names a rule directory: pass (checked when this table was
  generated).
- Every recommended pack is one the spec lists: pass.
- Interactive page published: FAIL. No page-publishing tool was available to
  the session, so this document is the only review surface. An operator
  session must publish the page (or accept answering in this document), then
  put its URL in the header.

## Items

| Rule | Kind | Title | Recommended pack | Reason |
|---|---|---|---|---|
| `a1` | question | External call envelope | `error-handling` | an exception envelope, translation or Raises check |
| `a10` | question | Predicate semantics | `style-and-naming` | naming, ordering, annotation or formatting style |
| `a11` | question | Exhaustion via assert_never | `error-handling` | makes error flow checkable (exhaustion, asserts) |
| `a12` | question | assert misuse | `error-handling` | makes error flow checkable (exhaustion, asserts) |
| `a13` | question | Same value to multiple structural slots | `state-and-effects` | mutation, purity or side effects |
| `a14` | question | Repeated computation per request | `performance` | cost per request or in a hot path |
| `a15` | question | Duplicate constructor / serialisation logic | `duplication` | repeated code, literals or calls |
| `a16` | question | CLI entry envelope | `error-handling` | an exception envelope, translation or Raises check |
| `a17` | question | Public-surface drift | `module-surfaces` | a package's public surface, __init__ or re-exports |
| `a18` | question | Hot-path setup | `performance` | cost per request or in a hot path |
| `a19` | question | Wrong logger level for broad-except | `error-handling` | an exception envelope, translation or Raises check |
| `a2` | question | Except tuple coverage | `error-handling` | an exception envelope, translation or Raises check |
| `a20` | question | Mutable module-level singleton | `state-and-effects` | mutation, purity or side effects |
| `a21` | question | Lazy init race | `state-and-effects` | mutation, purity or side effects |
| `a22` | question | Fall-through after partial handling | `error-handling` | an exception envelope, translation or Raises check |
| `a23` | question | Discarded multi-return | `state-and-effects` | mutation, purity or side effects |
| `a24` | question | Identity of subprocess / shell-out calls | `performance` | cost per request or in a hot path |
| `a25` | question | Shallow immutable wrapper | `state-and-effects` | mutation, purity or side effects |
| `a3` | question | Domain-error layering | `error-handling` | an exception envelope, translation or Raises check |
| `a4` | question | Docstring `Raises` accuracy | `error-handling` | an exception envelope, translation or Raises check |
| `a5` | question | Two sources of truth | `state-and-effects` | mutation, purity or side effects |
| `a6` | question | Stage method dual-path | `state-and-effects` | mutation, purity or side effects |
| `a7` | question | Constructor purity | `state-and-effects` | mutation, purity or side effects |
| `a8` | question | Late dataclass mutation | `state-and-effects` | mutation, purity or side effects |
| `a9` | question | Pure-named function side effects | `state-and-effects` | mutation, purity or side effects |
| `annotated-all-assignment` | check | An annotated `__all__` in a project that guards `__all__` | `module-surfaces` | a package's public surface, __init__ or re-exports |
| `as-import` | check | An import with an `as` alias, where the project bans it | `imports` | import style, declaration or layering |
| `assert-never-missing` | check | A string dispatch that does not end in assert_never | `error-handling` | makes error flow checkable (exhaustion, asserts) |
| `asymmetric-exception-translation` | check | A helper whose every caller translates its exceptions | `error-handling` | an exception envelope, translation or Raises check |
| `bare-except-in-module-with-narrow-errors` | check | A module that mixes broad excepts with narrow error tuples | `error-handling` | an exception envelope, translation or Raises check |
| `bare-nonbuiltin-generic-annotation` | check | A bare non-builtin generic in an annotation | `style-and-naming` | naming, ordering, annotation or formatting style |
| `bare-parametric-annotation` | check | A bare builtin generic in an annotation | `style-and-naming` | naming, ordering, annotation or formatting style |
| `broad-except-wrong-level` | check | A broad except handler that logs below exception level | `error-handling` | an exception envelope, translation or Raises check |
| `build-name-has-side-effect` | check | A build or compute function that reads the clock or runs a process | `state-and-effects` | mutation, purity or side effects |
| `callback-hotpath-io` | check | Per-event I/O in a training callback | `performance` | cost per request or in a hot path |
| `cli-entry-missing-error-envelope` | check | A CLI entry point with no error envelope beside siblings that have one | `error-handling` | an exception envelope, translation or Raises check |
| `constructor-disk-io` | check | Disk I/O inside a constructor | `state-and-effects` | mutation, purity or side effects |
| `d1` | question | Declared in pyproject | `imports` | import style, declaration or layering |
| `d2` | question | Unused declarations | `imports` | import style, declaration or layering |
| `d3` | question | Lockfile coherence | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `dataclass-optional-always-set` | check | An optional dataclass field that every construction sets | `state-and-effects` | mutation, purity or side effects |
| `dead-local-init` | check | A local initialised and then always overwritten | `state-and-effects` | mutation, purity or side effects |
| `def-class-in-init` | check | A top-level def or class in an __init__.py | `module-surfaces` | a package's public surface, __init__ or re-exports |
| `discarded-tuple-return` | check | A call whose tuple result is discarded | `state-and-effects` | mutation, purity or side effects |
| `doc1` | question | AGENTS.md project structure | `documentation` | docs matching code |
| `doc2` | question | AGENTS.md tools and libraries list | `documentation` | docs matching code |
| `doc3` | question | README.md and AGENTS.md | `documentation` | docs matching code |
| `doc4` | question | Specs match implementation | `documentation` | docs matching code |
| `doc5` | question | User docs match implementation | `documentation` | docs matching code |
| `docstring-raises-mismatch` | check | A docstring that names a different error from the one the body raises | `error-handling` | an exception envelope, translation or Raises check |
| `duplicate-call-sequence` | check | Two functions share a long call skeleton | `duplication` | repeated code, literals or calls |
| `duplicate-side-effect-per-target` | check | Two methods of a class sink to the same attribute target | `duplication` | repeated code, literals or calls |
| `duplicated-word` | check | The same word twice in a row in a comment or string | `style-and-naming` | naming, ordering, annotation or formatting style |
| `empty-init-while-siblings-export` | check | An empty subpackage init beside exporting siblings | `module-surfaces` | a package's public surface, __init__ or re-exports |
| `except-interpolation` | check | A caught exception interpolated into a new message | `error-handling` | an exception envelope, translation or Raises check |
| `failure-as-absence` | check | A caught exception or non-200 that returns a clean empty value | `error-handling` | an exception envelope, translation or Raises check |
| `filesystem-envelope-gap` | check | A narrow except around a filesystem-touching call that omits OSError | `error-handling` | an exception envelope, translation or Raises check |
| `filesystem-op-without-envelope` | check | A public entry point that touches the filesystem outside any try | `error-handling` | an exception envelope, translation or Raises check |
| `from-import` | check | A from-import outside an __init__.py | `imports` | import style, declaration or layering |
| `get-container-default-then-method-call` | check | A `.get(key, {})` default whose result is later called as if never None | `state-and-effects` | mutation, purity or side effects |
| `in-function-import` | check | An import inside a function | `imports` | import style, declaration or layering |
| `inconsistent-error-translation` | check | One domain error translated to different classes by different callers | `error-handling` | an exception envelope, translation or Raises check |
| `layer-has-domain-error-raises-stdlib` | check | A stdlib raise in a package that defines a domain error | `error-handling` | an exception envelope, translation or Raises check |
| `layering-violation` | check | An upward import against the declared package layering | `imports` | import style, declaration or layering |
| `leading-underscore-binding` | check | A leading-underscore parameter or bound name | `style-and-naming` | naming, ordering, annotation or formatting style |
| `legacy-formatting-percent` | check | C-printf formatting in a Python string | `style-and-naming` | naming, ordering, annotation or formatting style |
| `literal-duplication` | check | A string-literal collection repeated across files | `duplication` | repeated code, literals or calls |
| `lockfile-drift` | project-check | A lockfile out of date or unverifiable | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `logger-exception-graceful-degradation` | check | A handler that logs with logger.exception then returns a default | `error-handling` | an exception envelope, translation or Raises check |
| `migration-shim-consumer` | check | A consumer that imports through a re-export shim | `module-surfaces` | a package's public surface, __init__ or re-exports |
| `missing-raises-section` | check | A function that raises a project error with no Raises section | `error-handling` | an exception envelope, translation or Raises check |
| `mixed-raise-types` | check | A function that raises stdlib and project errors together | `error-handling` | an exception envelope, translation or Raises check |
| `mutable-members-in-immutable-wrapper` | check | An immutable wrapper that holds mutable members | `state-and-effects` | mutation, purity or side effects |
| `mutable-module-level-exported` | check | A mutable module-level container read from another module | `state-and-effects` | mutation, purity or side effects |
| `mutable-store-without-copy` | check | A constructor that stores a dict or list parameter by reference | `state-and-effects` | mutation, purity or side effects |
| `non-alphabetical-dict-keys` | check | A module-level dict whose string keys are not in sorted order | `style-and-naming` | naming, ordering, annotation or formatting style |
| `non-alphabetical-literal` | check | A module-level string collection not in sorted order | `style-and-naming` | naming, ordering, annotation or formatting style |
| `p1` | question | O(n^2) on real-size inputs | `performance` | cost per request or in a hot path |
| `p2` | question | Blocking I/O in hot paths | `performance` | cost per request or in a hot path |
| `p3` | question | Repeated expensive computation per request | `performance` | cost per request or in a hot path |
| `paired-sibling-helpers` | check | Identical function bodies in two or more files | `duplication` | repeated code, literals or calls |
| `parameter-mutation-in-pure-function` | check | A function named as pure that mutates its argument | `state-and-effects` | mutation, purity or side effects |
| `passthrough-shim` | check | A module-level function that only forwards to another call | `module-surfaces` | a package's public surface, __init__ or re-exports |
| `phase-section-doc-reference` | check | A numbered Phase or Section reference in a docstring or comment | `style-and-naming` | naming, ordering, annotation or formatting style |
| `pure-name-has-side-effect` | check | A function named as a query that does I/O | `state-and-effects` | mutation, purity or side effects |
| `raises-section-drift` | check | A Raises section that disagrees with the domain errors reaching the caller | `error-handling` | an exception envelope, translation or Raises check |
| `recompile-duplication` | check | The same regex constant name in two files | `duplication` | repeated code, literals or calls |
| `redundant-sink-caller-plus-callee` | check | A caller repeats its helper's sink call | `duplication` | repeated code, literals or calls |
| `reexport-in-non-init` | check | A re-export assignment in a file other than an __init__.py | `module-surfaces` | a package's public surface, __init__ or re-exports |
| `return-shadows-instance-attr` | check | A method that returns a divergent copy of an instance attribute | `state-and-effects` | mutation, purity or side effects |
| `ruff` | check | Lint and format findings from ruff | `style-and-naming` | naming, ordering, annotation or formatting style |
| `ruff-version-drift` | project-check | The audit ruff differs from the pre-commit pin | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `s1` | question | Type annotations on every signature | `style-and-naming` | naming, ordering, annotation or formatting style |
| `s2` | question | PascalCase / UPPER_SNAKE / lower_snake | `style-and-naming` | naming, ordering, annotation or formatting style |
| `s3` | question | TYPE_CHECKING block placement | `style-and-naming` | naming, ordering, annotation or formatting style |
| `s4` | question | Project-specific rule files | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `sec1` | question | Secrets in source | `security` | a security topic |
| `sec2` | question | Input validation at system boundaries | `security` | a security topic |
| `sec3` | question | Command injection | `security` | a security topic |
| `sec4` | question | Path traversal | `security` | a security topic |
| `sec5` | question | PII in logs | `security` | a security topic |
| `sibling-errors-no-common-base` | check | Error classes in one errors module with no shared parent | `error-handling` | an exception envelope, translation or Raises check |
| `silent-broad-except` | check | A broad except handler that neither logs nor re-raises | `error-handling` | an exception envelope, translation or Raises check |
| `silent-self-mutation` | check | A method that quietly reassigns state its caller supplied | `state-and-effects` | mutation, purity or side effects |
| `spec-api-signature-drift` | project-check | A spec API signature that differs from the source | `documentation` | docs matching code |
| `std-alphabetical-ordering` | standard | Alphabetical ordering | `style-and-naming` | naming, ordering, annotation or formatting style |
| `std-before-committing-and-pushing` | standard | Before committing and pushing | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `std-clean-init-py-files` | standard | Clean `__init__.py` files | `module-surfaces` | a package's public surface, __init__ or re-exports |
| `std-commands` | standard | Commands | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `std-comments` | standard | Comments | `style-and-naming` | naming, ordering, annotation or formatting style |
| `std-critical-rules` | standard | Critical rules | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `std-data-structures` | standard | Data structures | `style-and-naming` | naming, ordering, annotation or formatting style |
| `std-dependencies-python-version` | standard | Python version | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `std-error-handling` | standard | Error handling | `error-handling` | a standard enforced by the error-handling checks |
| `std-exception-syntax` | standard | Exception syntax | `error-handling` | a standard enforced by the error-handling checks |
| `std-imports-in-init-files` | standard | imports in `__init__.py` files | `imports` | import style, declaration or layering |
| `std-logging` | standard | Logging | `error-handling` | a standard enforced by the error-handling checks |
| `std-logging-exceptions` | standard | Logging exceptions | `error-handling` | a standard enforced by the error-handling checks |
| `std-naming` | standard | Naming | `style-and-naming` | naming, ordering, annotation or formatting style |
| `std-no-as-imports` | standard | No 'as' imports | `imports` | import style, declaration or layering |
| `std-no-leading-underscores` | standard | No leading underscores | `style-and-naming` | naming, ordering, annotation or formatting style |
| `std-project-structure` | standard | Project structure | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `std-python-version` | standard | Python version | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `std-string-formatting` | standard | String formatting | `style-and-naming` | naming, ordering, annotation or formatting style |
| `std-the-lockfile` | standard | The lockfile | `project-hygiene` | dependencies, lockfile, tooling or project files |
| `std-type-annotations` | standard | Type annotations | `style-and-naming` | naming, ordering, annotation or formatting style |
| `subprocess-without-memoisation` | check | A subprocess call in a function that is not memoised | `performance` | cost per request or in a hot path |
| `t1` | question | Test coverage of branchy logic | `testing` | test coverage and balance |
| `t2` | question | Property-based tests | `testing` | test coverage and balance |
| `t3` | question | Integration vs unit balance | `testing` | test coverage and balance |
| `text-patterns` | check | A source line that matches a text pattern | `style-and-naming` | naming, ordering, annotation or formatting style |
| `translator-envelope-gap` | check | A translating envelope whose except tuple omits an error its call raises | `error-handling` | an exception envelope, translation or Raises check |
| `try-wrapping-with-block-too-broad` | check | A handler that re-runs the work of the with block it wraps | `error-handling` | an exception envelope, translation or Raises check |
| `typing-deprecated-alias` | check | A `typing` alias that PEP 585 deprecated | `style-and-naming` | naming, ordering, annotation or formatting style |
| `underscore-forloop-target-read` | check | A leading-underscore loop target read inside the loop | `style-and-naming` | naming, ordering, annotation or formatting style |
| `underscore-unpack-target-read` | check | An unpacked leading-underscore name that is later read | `style-and-naming` | naming, ordering, annotation or formatting style |
| `unused-submodule-import` | check | A dotted import whose name the file never uses | `imports` | import style, declaration or layering |

### Items needing attention

None of the rules lacks an explanation, but these recommendations are the
least clear-cut, because the rule fits two packs:

- `a10` (predicate semantics) is placed in `style-and-naming` because it is
  about whether a name tells the truth; `state-and-effects` is the
  alternative.
- `a13` (same value to several slots), `a23` and `discarded-tuple-return`
  (discarded multi-return) are placed in `state-and-effects`; `a13` could
  equally sit in `duplication`, and the other two in `error-handling`.
- `std-logging` is placed in `error-handling`, following the spec's own
  description of that pack ("logging of failures"), though it covers logging
  generally.
- `std-data-structures` is placed in `style-and-naming`; no pack is on
  data-structure choice.
- `std-critical-rules` and `std-commands` are placed in `project-hygiene`
  because they name tools and files the project must not change.

## Decisions

No decision is open beyond the per-item answers above. Each item's
consequence is the same: the chosen pack decides which rules start
uncommented in `selection.txt` when a user picks that pack with `--pack`.

## Answers

Left empty for the user's verdict, one line per rule, filled in afterwards
with the date.
