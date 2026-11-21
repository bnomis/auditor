# Tasks: Listed Phase B documentation questions

**Spec:** `agents/specs/listed-phase-b-documentation-questions/spec.md`
**Created:** 2026-11-20
**Version:** 1

Implements the whole spec, version 1.1: the shared `corpus_definitions`
helper in `core.py`, the `docrefs.py` module (sections, code-shaped names,
resolution), the Doc1, Doc2, Doc4 and Doc5 listers with their briefs, the
per-question batch size, and the `SKILL.md` changes that put those questions
on the listed path and settle how every other question is sampled. Every
decision the spec needs is answered in its Decisions section (operator,
2026-11-20); no task here asks for one.

This list runs after `agents/tasks/repeatable-phase-b/tasks-1.md` has merged
to `main`: it builds on that list's `phaseb` package (`Candidate`, the
registry, the ledger, `phaseb.py`) and on the shared call resolver its Task 1
puts in `core.py`. Task 1's first subtask checks this and stops the list as
`blocked` if it does not hold.

No check is added to or removed from `CHECKS`, so
`claude/skills/auditme/checks/auditme/registry.py` and
`claude/skills/auditme/tests/registry-order.txt` stay as they are. No rule's
output changes: `check_spec_api_signature_drift` calls `corpus_definitions`
at its default (`classes=False`), which is exactly what `_source_definitions`
returns now. Every existing test in a touched test file must pass unchanged;
a task that needs to change one stops as `blocked` and names it.

Every task runs unattended: none calls an LLM, makes a network request or
reads another repository. Running the new listed questions on a real project
(the spec's pilot, run twice as A4's was) is the operator's step after the
list ships, not a task here.

The repository has no affected-tests tool. Each task names its own test
files; the last task runs every test tree the change can reach. Test commands
run from the repository root. Tests use neutral fixture names (`pkg`,
`probe`, `Probe`, `AppSettings`), as the shared repository's
`no-project-names` hook requires.

The new `docrefs.py` and the Doc listers are modelled on two siblings: the A4
lister in `phaseb/candidates.py` (registration, candidate shape, hashing) and
the spec-drift rule code in `rules/project_hygiene.py` (`_spec_markdown_files`,
`_DEF_LINE_RE`, `_CLASS_LINE_RE`, the `API`-heading fence walk). The last task
hoists what they duplicate.

---

## Task 1: Prerequisite check, and hoist `corpus_definitions` into `core.py`

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Module location (prerequisite; `core.py`); API (`corpus_definitions`); Error handling (syntax errors skipped; no sweep rule added)

**Technical Goal:** Confirm the repeatable-phase-b work has merged, then move
`_source_definitions` from `rules/project_hygiene.py` to a public
`corpus_definitions(scope, src_root, *, classes=False)` in
`checks/auditme/core.py`. With `classes=True` it also records classes and
their methods by bare name; at the default it returns exactly what
`_source_definitions` does now, and `check_spec_api_signature_drift` calls
it at the default.

**Subtasks:**

- [x] Prerequisite check, from the repository root: `grep -c '^\*\*Status:\*\* implemented' agents/specs/repeatable-phase-b/spec.md` prints `1`, and `python3 claude/skills/auditme/checks/phaseb.py candidates . --question A4` exits 0. If either fails, stop as `blocked`, naming the unmerged prerequisite `agents/tasks/repeatable-phase-b/tasks-1.md` and which check failed
- [x] Starting-point check: `grep -rnwE 'corpus_definitions|docrefs|DocSection|DocTarget|CorpusIndex|read_sections|resolve_name' claude/skills/auditme/checks` prints nothing; if it prints anything, stop as `blocked` and name what it found
- [x] Tests first in `claude/skills/auditme/tests/test_core.py`, under a new `# corpus definitions` heading, on a fixture project with `src/pkg/`: at the default, a module-level `def` is keyed by its bare name, a method and a class are not, and a file with a syntax error is skipped; with `classes=True`, a class is keyed by its name and a method by its bare name, each with its node and path; a name defined in two modules has two entries. Run them and see them fail
- [x] Add `corpus_definitions` to `claude/skills/auditme/checks/auditme/core.py`, carrying `_source_definitions`' docstring (corpus-wide, module-level by default, and why) and saying what `classes=True` adds and that only the Phase B listers set it
- [x] `_corpus_py_files` lives in `rules/state_and_effects.py`, and `core.py` imports nothing from `rules/`: move `_corpus_py_files` (and anything it needs that `core.py` lacks) into `core.py` and import it back into `state_and_effects.py` and `project_hygiene.py` under the same name, rather than adding a `core` to `rules` import
- [x] Remove `_source_definitions` and have `check_spec_api_signature_drift` call `corpus_definitions(scope, src_root)` with no `classes` argument; update the `_source_definitions` references in its docstring

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every existing test in `claude/skills/auditme/tests/test_nested_underscore_and_spec_signatures.py`, `claude/skills/auditme/tests/test_project_hygiene.py` and `claude/skills/auditme/tests/test_state_and_effects.py` passes unchanged
- [x] `check_spec_api_signature_drift` passes no `classes` argument
- [x] `core.py` imports nothing from `auditme.rules`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/test_core.py claude/skills/auditme/tests/test_nested_underscore_and_spec_signatures.py claude/skills/auditme/tests/test_project_hygiene.py claude/skills/auditme/tests/test_state_and_effects.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on `agents/tasks/repeatable-phase-b/tasks-1.md` (all tasks, merged to `main`)
- Key code: `_source_definitions` and `check_spec_api_signature_drift` in `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`; `_corpus_py_files` in `claude/skills/auditme/checks/auditme/rules/state_and_effects.py`
- If keeping `check_spec_api_signature_drift`'s output unchanged would need any existing test to change, stop as `blocked` and name the test

---

## Task 2: A registered batch size per question

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** API (`register_question` with `batch_size`); Settings

**Technical Goal:** Extend repeatable-phase-b's `register_question` with
`batch_size: int = 48`, keep it beside the brief in the registry, and have
`phaseb.py plan` use the question's registered size when `--batch-size` is
not given. A4 keeps 48, so its behaviour does not change.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_model.py` and `claude/skills/auditme/tests/phaseb/test_cli.py`: a question registered without a size reads back 48; one registered with 12 reads back 12; `phaseb.py plan` on a question registered with a small size writes batches of that size when `--batch-size` is absent, and of the given size when it is present. Run them and see them fail
- [x] Add the parameter and a reader for a question's batch size in `claude/skills/auditme/checks/auditme/phaseb/candidates.py`
- [x] Make `--batch-size` in `claude/skills/auditme/checks/phaseb.py` default to `None` and fall back to the registered size; say so in its help text

**Acceptance Criteria:**

- [x] The new tests pass
- [x] Every existing test under `claude/skills/auditme/tests/phaseb/` passes unchanged
- [x] A4 is registered with no explicit size, or with 48

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1 (the prerequisite check)
- `--depth` stays A4's option; the Doc listers ignore it

---

## Task 3: `docrefs.py`: sections and code-shaped names

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** API (`DocSection`, `read_sections`); Implementation (Documents and names); Error handling (unreadable document); Settings (constants)

**Technical Goal:** Add `claude/skills/auditme/checks/auditme/phaseb/docrefs.py`
with the frozen `DocSection` dataclass and `read_sections`, which splits a
markdown file into sections (a heading to the next heading of any level,
outside fences) and records each code-shaped name with its line.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_docrefs.py`: nested headings give a `heading_path` joined by ` > `; a repeated heading path gets `#2`; a `#` line inside a fence is not a heading; each name shape is kept (a path holding `/`, a path ending in each listed extension, `--name`, an identifier with `_`, `.` or an inner capital, a token with a trailing `(...)` dropped) and each is dropped (a token with a space or `<`, a path starting `/` or `~`, a plain lowercase word, a plain capitalised word); a `def` or `class` line in a fence under an `API` heading yields its name, and one under another heading does not; names come back in line order; a file that cannot be decoded as UTF-8, and a path that is a directory, raise `PhaseBError`. Run them and see them fail
- [x] Implement `DocSection` and `read_sections` with the spec's fields and docstrings; keep the path-shaped extensions and the Doc1 tree depth (3) as module constants
- [x] Reuse `_DEF_LINE_RE` and `_CLASS_LINE_RE` from `rules/project_hygiene.py` by import, not by copy

**Acceptance Criteria:**

- [x] The new tests pass
- [x] `read_sections` raises `PhaseBError`, never skips, on a file it cannot read

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb/test_docrefs.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Task 1
- A token's line is the line it appears on, not the section's start

---

## Task 4: `docrefs.py`: the corpus index and `resolve_name`

**Status:** done
**Priority:** high
**Complexity:** large
**Spec Reference:** API (`DocTarget`, `resolve_name`, `CorpusIndex`); Implementation (Resolution); Error handling (syntax errors; unresolved is not an error)

**Technical Goal:** Add `DocTarget`, a `CorpusIndex` built once per lister
call (from `corpus_definitions(..., classes=True)`, the shared resolver's
re-export alias table, settings fields, command-line options and the tracked
file list from `git ls-files -z`), and `resolve_name`, which tries each
resolution in the spec's order and returns `[]`, one target, or several when
ambiguous. Nothing resolves by resemblance.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_docrefs.py`, under a new `# resolution` heading, on a git-initialised fixture with `src/pkg/`, `agents/specs/probe/spec.md`, `docs/guide.md` and `AGENTS.md`: a tracked path relative to the root, and one relative to the document's directory, resolve to `file` or `directory`; an untracked path does not; a dotted name through a package `__init__.py` re-export resolves to the defining function; a unique bare name resolves to its `function` or `class`; a bare name defined twice returns both; `Probe.load` resolves to a `method` and `Probe.size` to a field; `app.port`, where `AppSettings(BaseSettings)` has a field `app` whose class has a field `port`, resolves to a `setting`, and a dotted key whose first segment is no settings field does not; `--limit`, passed to `add_argument`, `option` or `Option`, resolves to an `option`; a name the corpus never defines returns `[]`; each target carries `id`, `path`, `start` and `end`. Run them and see them fail
- [x] Implement `CorpusIndex`, using `corpus_definitions(..., classes=True)` from Task 1 and the alias table from repeatable-phase-b's shared call resolver in `core.py`, rather than building either again
- [x] Read the tracked file list with `git ls-files -z`; raise `PhaseBError` when it fails (no work tree)
- [x] Implement `DocTarget` and `resolve_name` with the spec's signatures and docstrings

**Acceptance Criteria:**

- [x] The new tests pass
- [x] A token that resolves to nothing or to several targets raises nothing
- [x] `git ls-files` failing raises `PhaseBError`

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb/test_docrefs.py claude/skills/auditme/tests/test_core.py -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 1 and 3
- A settings class is found by name (`BaseSettings` among its bases), not by importing pydantic: the checker uses the standard library only
- A Python file with a syntax error is skipped by the index, as `corpus_definitions` does

---

## Task 5: The Doc4 and Doc5 listers

**Status:** done
**Priority:** high
**Complexity:** large
**Spec Reference:** Implementation (Documents and names; Doc4 and Doc5 candidates); Decisions 2 and 3; Error handling

**Technical Goal:** Register `Doc4` (specs under `agents/specs/` whose
`**Status:**` is `implemented`) and `Doc5` (`docs/**/*.md` and the root
`README.md`) in `phaseb/candidates.py`: one candidate per (section, target)
pair and one `(unresolved)` candidate per section with unresolved or
ambiguous tokens, each with the spec's id, span, payload and hash.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_doc_candidates.py`, on a git-initialised fixture with `src/pkg/`, `agents/specs/probe/spec.md`, `docs/guide.md` and `AGENTS.md`: a proposed spec is not listed for Doc4 and an implemented one is; a root `README.md` is listed for Doc5 beside `docs/guide.md`; a pair's id is `<doc>::<heading path>::<target id>` and its payload holds the target and each line naming it; editing the target's source changes its pair's hash and not a pair in an unrelated section; editing a block of the section that names the target changes the hash, and editing a block that does not name it does not; a section with an undefined name gets `<doc>::<heading path>::(unresolved)` holding the token, its line and any definitions found, and that candidate vanishes once the name is defined; an ambiguous name goes into the `(unresolved)` candidate with both definitions; an unreadable listed document raises `PhaseBError`; candidates and hashes are the same on a second call. Run them and see them fail
- [x] Discover documents with `_spec_markdown_files` (imported, not copied), filtered as the spec says
- [x] Hash a pair as the spec's Doc4 and Doc5 candidates section says: sha256, NUL-separated, over each block (paragraph, list item, table row or fence) naming the target, once, in line order, then the target's source (`ast.get_source_segment` with decorators for a def or class, the statement for a field or option call, a file's bytes, a directory's sorted tracked entries); hash an `(unresolved)` candidate over the section's text and the sorted tokens
- [x] Register both with their brief paths (`claude/skills/auditme/phaseb/briefs/Doc4.md`, `Doc5.md`, written in Task 7) and batch size 24

**Acceptance Criteria:**

- [x] The new tests pass
- [x] No sweep rule is added: `claude/skills/auditme/tests/registry-order.txt` is unchanged

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 2, 3 and 4
- Model the registration and candidate shape on the A4 lister in the same module
- `Doc4.md` and `Doc5.md` exist as one-line placeholders (a version line only) because `test_briefs.py` requires every registered brief to exist; Task 7 replaces them

---

## Task 6: The Doc1 and Doc2 listers

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation (Doc1 and Doc2 candidates); Error handling (`pyproject.toml`, `.pre-commit-config.yaml`, `git ls-files`)

**Technical Goal:** Register `Doc1` and `Doc2` over the root `AGENTS.md`:
Doc1 one candidate per section that names a path or holds a fence, with the
tracked directory tree to depth 3; Doc2 one per section holding a backticked
token, matched against the declared distributions, the hook ids and the
corpus's top-level imports.

**Subtasks:**

- [x] Tests first in `claude/skills/auditme/tests/phaseb/test_doc_candidates.py`, under a new `# Doc1 and Doc2` heading: a Doc1 candidate's id is `AGENTS.md::<heading path>` and its payload holds each named path with its resolution and the tree; a section with neither path nor fence is not listed; a new tracked directory changes Doc1's hash and an untracked one does not; Doc2 matches a token to a PEP 503-normalised name from each of `project.dependencies`, `project.optional-dependencies`, `dependency-groups` and `build-system.requires`, to a `- id:` hook in `.pre-commit-config.yaml`, and to a top-level module the corpus imports, and lists a token matching none; editing `.pre-commit-config.yaml` changes Doc2's hash; an unparseable `pyproject.toml`, an unreadable `.pre-commit-config.yaml` and a failing `git ls-files` each raise `PhaseBError`; a missing `pyproject.toml` or hook file is not an error. Run them and see them fail
- [x] Build the tree from `git ls-files -z`, reusing Task 4's tracked-file reader; read `pyproject.toml` with `tomllib`; hash as the spec says (Doc1: section text, then tree; Doc2: section text, canonical JSON of the tables, then the hook file's bytes)
- [x] Register both with their brief paths (`claude/skills/auditme/phaseb/briefs/Doc1.md`, `Doc2.md`) and batch size 12

**Acceptance Criteria:**

- [x] The new tests pass
- [x] No code path treats a file that exists but cannot be read or parsed as absent

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 2, 3 and 4
- The `- id:` lines are read as text lines, as the spec says, so the lister needs no YAML library

---

## Task 7: The Doc1, Doc2, Doc4 and Doc5 briefs, version 1

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation (Briefs; Skill changes, Doc5's predicate); Decision 3

**Technical Goal:** Write `claude/skills/auditme/phaseb/briefs/{Doc1,Doc2,Doc4,Doc5}.md`
in the A4 brief's form: the question verbatim from `SKILL.md`, the spec's
thresholds, the input and output format, the env-variable security rule, and
`**Brief version:** 1`.

**Subtasks:**

- [x] In `claude/skills/auditme/SKILL.md`'s Phase B checklist, change Doc5's predicate to "Drift between `docs/` or `README.md` and `src/`" (decision 3), so the Doc5 brief quotes the widened question
- [x] Extend `claude/skills/auditme/tests/phaseb/test_briefs.py`: each Doc brief exists with exactly one `**Brief version:** 1` line; each contains its question's text as it stands in `SKILL.md`; Doc4 and Doc5 name the `drift` key, Doc1 and Doc2 the `stale` and `missing` keys. Run them and see them fail
- [x] Write each brief's thresholds exactly as the spec's Briefs section lists them, including what is not drift and, for Doc4 and Doc5, how an `(unresolved)` candidate is judged
- [x] Output: one JSON line per candidate with `id`, its findings keys and `reason`, every candidate present; a threshold the brief does not settle is reported in the reply, not decided
- [x] Repeat the security rule every subagent brief carries: never list environment variables (`env`, `printenv`, `set`) or print an env file; to test that a variable is set, use `[ -n "${VAR:-}" ]` and print only yes or no

**Acceptance Criteria:**

- [x] The new tests pass
- [x] No brief names a project, path or review from any real run

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb -q -p no:cacheprovider` passes

**Notes:**

- Depends on Tasks 5 and 6
- Model each on `claude/skills/auditme/phaseb/briefs/A4.md`

---

## Task 8: `SKILL.md`: listed Doc questions and sampled cadence

**Status:** done
**Priority:** high
**Complexity:** medium
**Spec Reference:** Implementation (Skill changes); Decisions 1, 2 and 3

**Technical Goal:** Update `claude/skills/auditme/SKILL.md` so Phase B runs
A4, Doc1, Doc2, Doc4 and Doc5 on the listed path and every other question
sampled, on changed files every audit and on the whole tree every third
audit, with the review template and completion gate to match.

**Subtasks:**

- [x] In section 4, Interpretive review, name the listed questions (A4, Doc1, Doc2, Doc4, Doc5) and state the sampled cadence: every audit runs a sampled question on the files changed since the previous review's `**Commit:**`, using the diff base `checks/changed.py` resolves; every third audit, counted from the first audit after this change ships, and any audit with no previous `**Commit:**`, runs it on the whole tree
- [x] Beside Doc5's predicate (widened in Task 7), say the first audit's README findings are catch-up
- [x] In the Convergence section, say a sampled question's new site goes under "Coverage (sampled)" and is never marked "missed by" a review, and the rule applies in full to listed questions
- [x] In the Review template, add a `**Commit:**` line (the audited `HEAD`) and, beside each sampled question, its mode (changed files since a named commit, or full)
- [x] In the Completion gate, require a current verdict per candidate for every listed question and that every sampled question ran in its cadence's mode
- [x] Say the next audit after this change judges every Doc candidate, that its findings in unchanged code are catch-up, and that its Convergence note names the newly listed questions
- [x] Add the new test files to `claude/skills/auditme/tests/README.md`'s description of the test tree

**Acceptance Criteria:**

- [x] `SKILL.md` names each listed question and the sampled cadence as the spec states them
- [x] Nothing in `SKILL.md` names a project, path or review from any real run

**Definition of Done:**

- [x] The task's commit passes its pre-commit hooks (never `--no-verify`)
- [x] `uv run --no-project --with pytest pytest claude/skills/auditme/tests/phaseb/test_briefs.py -q -p no:cacheprovider` passes (each brief still quotes its question verbatim)
- [x] `uv run --group docs mkdocs build --strict` passes

**Notes:**

- Depends on Task 7
- This is the skill change the spec says ships between audits; nothing here runs an audit

---

## Task 9: Deduplication, whole-tree checks, final tests, and close the spec

**Status:** done
**Priority:** high
**Complexity:** small
**Spec Reference:** whole spec

**Technical Goal:** Remove any duplication the new modules introduced, run
every whole-tree check, save the final full test run to the order's test log,
and mark the spec implemented.

**Subtasks:**

- [x] Hoist anything `docrefs.py` and the Doc listers duplicate from the A4 lister (`phaseb/candidates.py`) or the spec-drift rule code (`rules/project_hygiene.py`: `_spec_markdown_files`, `_DEF_LINE_RE`, `_CLASS_LINE_RE`, the `API`-heading and fence tracking, the `**Status:**` reading) to a single owner: grep the tree for each literal collection, constant and one-line helper the new modules define, and import rather than copy. Choose the owner from the existing import graph; prefer a module the consumer already imports over adding a new edge. A hoist that would change `check_spec_api_signature_drift`'s output or need one of its existing tests to change stops as `blocked`, naming the test
- [x] For each of `Doc1`, `Doc2`, `Doc4` and `Doc5`, run `python3 claude/skills/auditme/checks/phaseb.py candidates . --question <Q>` from the repository root and check it exits 0 and that each line it prints parses as JSON with the `id`, `hash` and `payload` keys
- [x] Confirm `claude/skills/auditme/tests/registry-order.txt` and `claude/skills/auditme/checks/auditme/registry.py` are unchanged against the branch's base (`git diff <base> -- <path>` prints nothing)
- [x] Set the spec's `**Status:**` to `implemented`
- [x] Run `pre-commit run --all-files`, `pre-commit run auditme-all --hook-stage manual --all-files` and `uv run --group docs mkdocs build --strict`, and fix what they report
- [x] Last, save the final full test run to the order's test log, relative to the main checkout:
      `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p'); LOG="$MAIN/logs/rro/listed-phase-b-documentation-questions/tasks-1/final-tests.log"; mkdir -p "$(dirname "$LOG")"; uv run --no-project --with pytest --with pyyaml pytest claude/skills/auditme/tests claude/skills/project-setup/tests tests -q -p no:cacheprovider 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ] && echo 'all selected test directories passed' | tee -a "$LOG"`

**Acceptance Criteria:**

- [x] No literal collection or helper is defined both in `phaseb/` and elsewhere under `claude/skills/auditme/checks/`
- [x] Every existing `check_spec_api_signature_drift` test passes unchanged
- [x] The spec's status is `implemented`
- [x] The log ends with `all selected test directories passed`, printed only because pytest exited 0

**Definition of Done:**

- [x] `pre-commit run --all-files` exits 0
- [x] `pre-commit run auditme-all --hook-stage manual --all-files` exits 0
- [x] `uv run --group docs mkdocs build --strict` passes
- [x] The final test command above exits 0 and writes its pass line to `logs/rro/listed-phase-b-documentation-questions/tasks-1/final-tests.log` under the main checkout

**Notes:**

- Depends on Tasks 1-8
- No `TODO.md` item moves to `DONE.md` here: the item "Put the Phase B questions that find most onto the listed path" covers more than this spec's group and is closed by the architecture-questions list, which runs later in the order
- The spec's pilot (the operator's first run of the new listed questions on a real project, run twice as A4's was, with any threshold it exposes landing as a brief version bump) is the operator's step after this list ships, not a task
- The test log is a run record outside the repository's tracked files; do not commit it

---
