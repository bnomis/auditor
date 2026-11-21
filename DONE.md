# DONE

Finished work, chronological, newest last. An item moves here from `TODO.md`
unchanged, followed by a `Done:` line. Never file a new item here.

## A new project cannot commit Python without a `src/<package>/` layout

Found on 2026-10-31 while walking "A new project" in `docs/setup.md` in a
throwaway repository whose hooks were pinned at `3974fbb`. Committing
`bin/tool.py` failed `auditme-changed` with `the audit sweep exited 2:
ERROR: <repo>/src does not exist`. Committing a loose `src/a.py` failed with
`ERROR: no package under <repo>/src`. Only a commit with
`src/<package>/__init__.py` passed. Neither `docs/setup.md` nor the
`/project-setup new` skill mentions this layout, and `new` is meant for an
empty repository.

Cause: `main()` in `claude/skills/auditme/checks/audit.py` returns 2 when
`<scope>/src` is missing, or when `auditme.core._audit_roots()` finds no
package under it. It does this before `bin/` is considered, even though
`bin/` is one of the default extra roots (`EXTRA_ROOT_NAMES` in
`checks/auditme/core.py`). `checks/changed.py` treats any non-zero sweep exit
as a failure, so every commit that touches a `.py` file is blocked.

Fix direction: decide between two approaches. (a) The checker audits
whatever roots exist, so a project with no `src/` passes over `bin/` alone
and exits 0 when no root exists. (b) `/project-setup new` creates
`src/<project>/__init__.py`, and the guide states the layout. Option (a)
changes the checker's contract for every project, so it goes through the
project-setup spec first. Option (b) needs only a sentence in the spec and
in the guide.

Note 2026-10-31: the operator chose (a), and to report a `.py` file directly
in `src/` as a `src-loose-module` hit. Spec:
`agents/specs/project-setup/spec.md` (amendment 1.2); tasks:
`agents/tasks/project-setup/tasks-2.md`.

Done: 2026-10-31 - b7f0e08, 8cb8502, 81212a5 (Tasks 1-3 of tasks-2.md); spec amendment 1.2; `agents/tasks/project-setup/tasks-2.md`.

## The setup installs a `pre-push` hook that runs no audit check

Found on 2026-10-31 while walking "A new project" in `docs/setup.md`. The
`/project-setup` skill and the guide both run `pre-commit install
--hook-type pre-commit --hook-type pre-push`. But `.pre-commit-hooks.yaml`
publishes `auditme-changed` at `stages: [pre-commit]` and `auditme-all` at
`stages: [manual]`, and the template `.pre-commit-config.yaml` overrides
neither. So the `pre-push` hook git runs on each push checks nothing. The
shared rule `claude/rules/git-conventions.md` ("A rule a script can check is
a hook") says whole-tree checks run as a `pre-push` hook, and in CI.

Cause: the project-setup spec (`agents/specs/project-setup/spec.md`, "API")
put the whole-tree sweep at the manual stage and in CI only. The rule asks
for a `pre-push` stage as well. Nothing reconciles the two.

Fix direction: decide which one holds. Either add `pre-push` to
`auditme-all`'s stages (in `.pre-commit-hooks.yaml`, or in the template
config), which costs a whole-tree sweep on every push, or drop the
`pre-push` install from the skill, the guide and the rule. Whichever is
chosen, change the spec first.

Done: 2026-10-31 - the operator chose to switch the push gate on with the CI gate: the `new` template sets `stages: [manual, pre-push]` on `auditme-all`, `adopt` adds it only at zero hits, and the manifest keeps `[manual]`; `changed.py --all` names `SKIP=auditme-all git push`; spec amendment 1.3; branch `fix/audit-on-push`.

## Adopt the shared guards in each project

The shared guards exist, but no project uses them yet. Each open finding below
is closed by adopting them, and adopting the first project with a CI gate is
also the real CI run and the real deploy key that the end-to-end check never
did.

Found on 2026-10-31 by `/todo-review`. Task 9 of
`agents/tasks/project-setup/tasks-1.md` lists, in its Notes, the operator
steps for after the merge: run `bin/install-claude.py` on the real machine
(done: `~/.claude/settings.json` registers `auditme-stop.sh`, linked at 14:25
on 2026-10-31); `/project-setup adopt` in each project, the motivating one
first; and an `AGENTS_DEPLOY_KEY` for each project that enables the CI gate.
On 2026-10-31, none of the 7 repositories beside this one with a
`.pre-commit-config.yaml` carried an audit hook. Nor did this repository,
and a scratch run of the patched checker on it that day found 12 unaccepted
hits in `bin/`.

Fix direction: settle "The setup installs a `pre-push` hook that runs no audit
check" first, so no project is set up twice. Then run `/project-setup adopt`
in this repository, fixing or accepting its hits, and enable its CI gate with
a deploy key. That run is the real CI run and deploy key from the first
finding. Then adopt the motivating project, then the rest.

Note 2026-10-31: the `pre-push` item is settled and in `DONE.md`. `adopt` now
turns on the push stage together with the CI gate, once a project has zero hits.

Note 2026-10-31: this repository is adopted, on branch `feat/adopt-audit-hooks`.
Its 12 hits, all in `bin/install-claude.py`, were fixed, none accepted. The
operator chose `repo: local` hooks that run the checker from the working
tree, so no deploy key is needed here, plus a new `.github/workflows/ci.yml`.
Writing that workflow exposed two defects in
`claude/skills/project-setup/templates/ci.yml`: it set up Python 3.12,
where the checker's `except A, B:` syntax does not parse, and it never
installed `pre-commit`. Both are fixed and tested. The first real CI run is
this repository's first push after the merge. The real deploy key is now
first tested at the next project to adopt.

Note 2026-10-31: this repository's first real CI run (GitHub Actions
`41217991678`, at `70a50a4`) failed the whole-tree audit. The checker runs a
bare `ruff`, which `uv sync` installs only into `.venv`, so the run reported
`ruff not installed`. Since `fef77ba`, the workflow and the CI template put
`.venv/bin` on `PATH`, and the next run (`41218182723`) passed every step.
What remains: adopting the motivating project and the rest, and the first
real deploy key.

### Project-setup end-to-end checks that were never run

Found on 2026-10-31, after the project-setup queue (task list
`agents/tasks/project-setup/tasks-1.md`, merged to `main` as `69fa821`).
Task 9, the end-to-end check, was marked done, but the body of its commit
`9d99176` says four of its checks did not run:

1. **`bin/install-claude.py` as a command against a temporary `HOME`.** The
   sandbox refused to redirect `HOME`. In-process,
   `tests/test_install_claude.py::test_full_install_into_temporary_home` calls
   `install_claude()` twice with `HOME` monkeypatched, but it only asserts
   the Stop hook registration and that `auditme-stop.sh` exists. Nothing runs
   the script from a shell or checks the rest of what it installs.
2. **Walking `docs/setup.md` as written.** The run only checked that the
   files and commands the guide names exist. It did not follow the "A new
   machine" and "A new project" sections step by step. Even so, the Task 9
   subtask for that walk and its acceptance criterion ("the guide's walked
   sections needed no step it does not state") were ticked. Both are
   unticked as of 2026-10-31.
3. **A real CI run** of the audit gate in `templates/ci.yml` and
   `templates/ci-audit-step.yml`.
4. **A real deploy key**: the `AGENTS_DEPLOY_KEY` secret that the CI templates
   read, following `docs/setup.md` "The deploy key".

Cause: the queue's sandbox could not redirect `HOME` and cannot reach GitHub.
The unrun checks were recorded only in a commit body, and the task list was
ticked anyway.

Fix direction: do this by hand, outside the sandbox. In a throwaway directory
with `HOME` set to a temporary path, run `bin/install-claude.py` and then walk
`docs/setup.md`'s "A new machine" and "A new project" sections exactly as
written. Fix every step the guide leaves unstated. Then, in one real project,
add the deploy key and push, so CI runs the audit gate once and fails on a
planted unaccepted hit. Tick the Task 9 subtask and criterion again once the
walk passes.

Note 2026-10-31: the walk was done by hand in a scratch directory, with
`HOME` set to a temporary path and a local clone of this repository, on
branch `fix/setup-walk`:

- With no `~/.claude`, `bin/install-claude.py` crashed with
  `FileNotFoundError` on the first file it linked, because
  `install_claude()` never created the directory. The existing test hid this
  by creating `~/.claude` first. Fixed: the directory is now created, and
  `test_install_into_home_without_claude_dir` covers it. With that fix, the
  guide's "Check it" commands pass.
- The skill's check for leftover placeholders (`grep -rn '{{'`) always hit
  `ci.yml`, because of GitHub's own `${{ secrets.AGENTS_DEPLOY_KEY }}`.
  Fixed in `claude/skills/project-setup/SKILL.md` to match
  `\{\{[A-Z_]+\}\}`.
- In "A new project", the hooks pinned over SSH install and run. A
  leading-underscore hit in a package file blocks the commit with a clear
  message, and `auditme-all` passes on a clean tree.
- Two more findings need a decision. They are filed as their own items:
  "A new project cannot commit Python without a `src/<package>/` layout" and
  "The setup installs a `pre-push` hook that runs no audit check".

Still open: a real CI run and a real deploy key. Both change GitHub, so the
operator must confirm them.

Note 2026-10-31: since `3607aa2` (the installer fix) and amendment 1.2 (the
`src/` layout, `tasks-2.md`), the installer run and the guide walk are done;
only the real CI run and the real deploy key remain.

Done: 2026-11-01 - every part that lives in this repository is done: this repository is adopted (its CI audit passes since run `41218182723`), the push gate is settled (spec amendment 1.3), and the real CI run and real deploy key were proven when two adopted projects' CI runs on 2026-11-01 passed "Install the audit deploy key", "Audit the whole tree" and "Remove the audit deploy key". Adopting each remaining project is that project's own work, recorded in its own `TODO.md`.

## The checker runs whatever `ruff` is on `PATH`, not the version the ruff hook pins

Found on 2026-11-01, recorded in an adopting project's own `TODO.md`: its
CI audit runs `ruff` from the project's `.venv`, where a dependency
cooldown had locked an older ruff than the `rev` of its pre-commit ruff
hook. Both versions passed the tree that day, but a later difference
between them would make the commit hook and the CI audit disagree.

Cause: `claude/skills/auditme/checks/auditme/rules/project_hygiene.py`
runs a bare `ruff check` and `ruff format --check`, so it uses whichever
ruff is first on `PATH`. `docs/setup.md` ("ruff on PATH") and the CI
template (`claude/skills/project-setup/templates/ci.yml`, "use the
project's locked one") point it at the project's `.venv`, and nothing
ties that version to the ruff hook's `rev`. Every adopting project has the
same gap.

Fix direction: at least, say in `docs/setup.md` and the CI template that
the locked ruff must equal the ruff hook's `rev`, and keep them equal when
either moves. Better, have the checker report the ruff version it ran, or
fail when it differs from the hook's `rev` in `.pre-commit-config.yaml`;
that changes the checker's behaviour, so it goes through the
project-setup spec first.

Spec: `agents/specs/project-setup/spec.md`, amendment 1.4; tasks: `agents/tasks/project-setup/tasks-3.md`.

Done: 2026-11-01 - spec amendment 1.4, agents/tasks/project-setup/tasks-3.md: the ruff-version-drift check, and this repository's ruff hook lowered to v0.17.1.

## The CI template says to pin actions to a commit SHA but pins tags

Found on 2026-11-01 in `claude/skills/project-setup/templates/ci.yml`,
whose comment reads "Pin third-party actions to a full commit SHA, and
let Dependabot update them", above `actions/setup-python@v7.1.0` and
`astral-sh/setup-uv@v10.3.3`, which are tags. This repository's own
`.github/workflows/ci.yml` pins tags too, and has a
`.github/dependabot.yml`.

Cause: the comment and the pins were never reconciled; the 2026-10-31
version bumps kept the tag form.

Fix direction: decide which holds. Either pin each action to its full
commit SHA, with the tag in a trailing comment, in the template and in
this repository's workflow, or drop the SHA advice from the comment. The
operator's call.

Done: 2026-11-01 - the operator chose tag pins over SHA pins: the template's comment now says to pin each third-party action to an exact release tag, and the pins are unchanged; branch `docs/ci-template-tag-pins`.

## auditme rules report hits the code does not have

Found on 2026-11-01 while clearing every unaccepted hit in another project,
which accepted each site with a marker and listed it in its own records. The
patterns, by rule:

- `raises-section-drift` attributes a callee's `Raises:` entry to a caller
  that cannot take the raising path: the caller passes an argument value
  that rules the error out (a fixed name, an optional argument left unset, a
  value every caller has already checked against the supported list), or
  passes only types the callee's dispatch error does not apply to, or calls
  the callee only inside a guard (`if is_model(x):`) that rules the error out.
- `raises-section-drift` reports an error caught in a nested function and
  re-raised on one branch with a bare `raise` as never reaching the caller.
- `missing-raises-section` counts a `raise` inside a nested function as
  reaching the caller when the enclosing function catches it, either by the
  exception's base class or because the nested function's only call sits in
  a `try`.
- `passthrough-shim` flags a wrapper whose single `return target(...)`
  computes its arguments, or reuses a parameter as a default
  (`table.get(name, name)`), and flags functions decorated `@pytest.fixture`,
  which tests request by name.
- `non-alphabetical-literal` flags an `__all__` in the order ruff RUF022
  requires (constants, classes, functions), which its ASCII order contradicts.

Cause: the rules decide from the shape of a call or a `raise` alone. The
`Raises:` rules do not follow argument values, guards or handlers within the
enclosing function; `passthrough-shim` does not check that the arguments are
the wrapper's parameters passed on unchanged; and the ordering rule has no
case for `__all__`.

Fix direction: one rule at a time, in `claude/skills/auditme/checks/`, each
with a test fixture for the false positive: skip a `raise` caught within the
same enclosing function, count a bare `raise` as raising the caught types,
flag a shim only when its arguments are its own parameters unchanged, skip
pytest fixtures, and accept the RUF022 order for `__all__`. Following
argument values and guards for `raises-section-drift` is the largest, and
may be better done as skipping callees whose raise depends on an argument;
decide that in a spec first. Each change frees the accept markers the other
project added, which it removes once it pins the change.

Spec: `agents/specs/auditme-false-positives/spec.md`; tasks: `agents/tasks/auditme-false-positives/tasks-1.md`.

Done: 2026-11-01 - agents/specs/auditme-false-positives/spec.md, agents/tasks/auditme-false-positives/tasks-1.md: the five refinements, documented in SKILL.md.

## The checker's docstrings and help, and the setup guide, disagree with the code

Found on 2026-11-01 while writing the documentation site's checker and
command-line pages, each checked against the code:

- The `changed.py` module docstring says "A sweep that cannot run fails; it
  is never skipped", but `main()` returns 0 without sweeping when no diff
  base resolves and when no reportable file changed (the two `return 0`
  branches before `sweep()` in `claude/skills/auditme/checks/changed.py`).
- `changed.py`'s `ACCEPT_HELP` tells the reader to accept any hit with an
  accept marker, but `ruff` and `lockfile-drift` hits are always emitted
  unaccepted (`claude/skills/auditme/checks/auditme/rules/project_hygiene.py`),
  so for those the advice cannot work.
- The `audit.py` docstring's output schema leaves out the `related` key that
  `core.py` emits and `changed.py` reads, and its acceptance list gives only
  the unscoped `# auditme: accept <reason>` marker, not the rule-scoped
  `accept[<rule>]` form the setup guide and `SKILL.md` recommend.
- `docs/setup.md` ("What you get") says directories other than `src/` and
  `bin/` are not swept, but `spec-api-signature-drift` reads every `.md`
  file under the project root outside the skipped directories, and the
  project-level checks read `pyproject.toml`, `uv.lock`,
  `.pre-commit-config.yaml` and `AGENTS.md`.
- `claude/statusline.py` is linked into `~/.claude/` by
  `bin/install-claude.py`, but nothing registers it as the status line, and
  `docs/setup.md` does not say to; on the operator's machine it is registered
  by hand in `~/.claude/settings.json`, so a new machine gets no status line.

Cause: the docstrings, help text and guide were written before the
behaviour they describe changed (the skip branches, the scoped marker, the
`related` key, the Markdown sweep), and the status line was set up by hand
outside the installer.

Fix direction: correct each text to match the code - say when `changed.py`
skips and why that is safe, give `ruff` and `lockfile-drift` their own fix
advice, add `related` and the scoped marker to the `audit.py` docstring, and
say in `docs/setup.md` what besides `src/` and `bin/` is read. For the status
line, either have the installer register it as it does the Stop hook, or add
the step to `docs/setup.md`; registering it changes the installer, so decide
that with the operator. No spec needed for the text fixes.

Done: 2026-11-01 - branch `fix/checker-docs-and-statusline`: the `changed.py` docstring says when it skips, ruff and lockfile-drift hits get their own advice (tests in `test_changed.py`), the `audit.py` docstring gains `related` and the scoped marker, `docs/setup.md` says what else is read, and `bin/install-claude.py` registers the status line unless one is set, as the operator chose (tests in `tests/test_install_claude.py`).

## spec-api-signature-drift compares a spec's method with a module-level function of the same name

Found on 2026-11-06 in a sweep of another project: two of its
`spec-api-signature-drift` hits were false. Each was a `@classmethod`
`load(cls, ...)` written inside a `class` block in a spec's API section,
reported as drifting from that project's one module-level `def load(path)`,
an unrelated function in another module. The real classmethods matched the
spec.

Cause: `_DEF_LINE_RE` in
`claude/skills/auditme/checks/auditme/rules/project_hygiene.py` allows
leading whitespace, so `check_spec_api_signature_drift` reads a method
indented inside a spec's `class` block as a `def`, and looks its bare name up
in `_source_definitions`, which holds module-level definitions only. The
rule's "a name with no module-level definition does not fire" refinement
then does not apply, because a module-level function happens to share the
name.

Fix direction: skip a spec `def` that sits inside a `class` block (indented
under a `class` line in the same fence), as the rule already skips methods on
the source side; or, more ambitiously, compare it with the method of that
class in the source. Add a test beside the existing refinements in
`claude/skills/auditme/tests/test_nested_underscore_and_spec_signatures.py`:
a spec class with a `load` classmethod and an unrelated module-level `load`
in the source does not fire. Small; no spec needed.

Done: 2026-11-06 - branch `fix/spec-signature-class-methods`: `check_spec_api_signature_drift` skips a `def` indented under a `class` line in the same spec fence; tests `test_a_method_in_a_spec_class_block_does_not_fire` and `test_a_module_level_def_after_a_spec_class_block_still_fires`.

## Put the Phase B questions that find most onto the listed path

Found on 2026-11-20 while writing `agents/specs/repeatable-phase-b/spec.md`
(version 1.1), which puts only A4 on the listed path: a program lists every
candidate, reviewers judge each against a versioned brief, and a ledger
reuses each verdict while its code is unchanged. Every other question is
still sampled, so it still turns up sites earlier audits missed in code
nobody changed. Measured the same day on one project's last three full
audits, counting the Phase B question each finding names (a finding may name
more than one): the documentation questions (Doc1, Doc2, Doc4, Doc5) 13;
the test questions T1 and T2 7; A1, A11, A17 and A19 9; A13 and A15 5; A4 3;
the rest 5. Listing A4 alone covers the smallest of these groups.

Cause: version 1 of the listed path covers one question, and nothing yet
says which come next or what happens to a question that cannot be listed.

Fix direction: an amendment of the repeatable-phase-b spec per group, in
this order, each with its lister, brief and tests, shipped between audits:

1. Doc4 and Doc5, then Doc1 and Doc2: a candidate is each backticked name
   in a spec or user document that resolves to a function, setting, class
   or file, with the code it names in the hash.
2. T1 and T2: branchy functions and the functions a property test would
   suit, from the AST, with their test files in the hash.
3. A11, A19, A1 and A17: the match statements, broad handlers, external
   calls and public surfaces the AST already finds.

The same spec settles a rule for the questions that stay sampled (A13, A15
and any whose candidates cannot be listed): run them on changed files only,
or every few audits, and report their new sites as coverage, not drift.

Spec: `agents/specs/listed-phase-b-documentation-questions/spec.md`, `agents/specs/listed-phase-b-test-questions/spec.md` and `agents/specs/listed-phase-b-architecture-questions/spec.md`, each a separate spec extending the repeatable-phase-b one rather than an amendment of it; tasks: `agents/tasks/listed-phase-b-documentation-questions/tasks-1.md`, `agents/tasks/listed-phase-b-test-questions/tasks-1.md` and `agents/tasks/listed-phase-b-architecture-questions/tasks-1.md`, in the run order `agents/tasks/order-raises-resolution-and-listed-phase-b.md`.

Done: 2026-11-20 - specs `agents/specs/listed-phase-b-documentation-questions/spec.md`, `agents/specs/listed-phase-b-test-questions/spec.md` and `agents/specs/listed-phase-b-architecture-questions/spec.md`, task lists `agents/tasks/listed-phase-b-documentation-questions/tasks-1.md`, `agents/tasks/listed-phase-b-test-questions/tasks-1.md` and `agents/tasks/listed-phase-b-architecture-questions/tasks-1.md`

## `raises-section-drift` misses errors reached through a section-less wrapper or a `Class.method()` call

Found on 2026-11-20 in a review of this file: the open request in
`claude/skills/auditme/requests.md`, raised the same day by an audit whose
Phase B A4 found by hand `Raises:` omissions the rule exists to catch, is
recorded in no `TODO.md` item. While it is open the next audit cannot start
(`claude/skills/auditme/SKILL.md`, the mechanical sweep's check that the
`## Open` section is empty). The rule in
`claude/skills/auditme/checks/auditme/rules/error_handling.py` was last
changed on 2026-11-01.

Cause: `check_raises_section_drift` follows a callee one level, through its
declared `Raises:` section, so a wrapper with no section contributes
nothing; and it does not resolve `<ClassName>.<method>(...)` calls.

Fix direction: as the request proposes, with its fixtures and its catch-up
run on each project with the shared hooks before the entry is deleted. The
`Class.method()` gap becomes the rule passing `class_methods=True` to the
shared resolver once Task 1 of `agents/tasks/repeatable-phase-b/tasks-1.md`
has moved it into `core.py`; the section-less wrapper gap is separate work.
The request entry stays the detailed record; this item tracks the work.

Spec: `agents/specs/raises-section-resolution/spec.md`; tasks: `agents/tasks/raises-section-resolution/tasks-1.md`, after `agents/tasks/repeatable-phase-b/tasks-1.md`, in the run order `agents/tasks/order-raises-resolution-and-listed-phase-b.md`. Stays open after the list ships, until the catch-up run in each project with the shared hooks is done and the `requests.md` entry is deleted.

Note, 2026-11-20: the code shipped the same day in `f1a24f4` (row 2 of the
run order), so the rule no longer dates from 2026-11-01: it follows a callee
with no `Raises:` section up to three calls deep and resolves
`<ClassName>.<method>(...)`, and it moved the A4 brief to version 2. What
remains is outside this repository: the catch-up run in each project with
the shared hooks, then deleting the entry under `## Open` in
`claude/skills/auditme/requests.md`, which is still there. The next audit
cannot start until it is gone.

Done: 2026-11-21 - code in `f1a24f4` (spec `agents/specs/raises-section-resolution/spec.md`, task list `agents/tasks/raises-section-resolution/tasks-1.md`); the catch-up landed on 2026-11-21 in every project with the shared hooks - `Raises:` entries where the error reaches the caller, scoped accept markers with a reason where it cannot, and each project's pin moved to `8d97d96` - and the `requests.md` entry was deleted.

## `phaseb.py check` rejects the result of every listed question but A4

Found on 2026-11-21 in the Doc batch-size pilot (two runs of 13 batches each
on one project, results kept in the session's scratchpad):
`python3 claude/skills/auditme/checks/phaseb.py check <run dir>` exits 1 on
every Doc1, Doc2, Doc4 and Doc5 run. It reports each result line as
`unparseable ... extra must be a list of strings` and each id as missing,
and lists every batch for retry, though every reviewer returned a
well-formed line per candidate in the brief's own shape. So no Doc run can
pass `check` or be merged into a ledger. Reading the code the same day: the
T1, T2, A1, A11, A17 and A19 briefs ask for a `findings` object, which the
same check rejects, so every listed question but A4 is affected.

Cause: `parse_result` in `claude/skills/auditme/checks/auditme/phaseb/batches.py`
requires A4's `missing` and `extra` lists on every line, and `read_run_verdicts`
in the same file builds each `Verdict.findings` from those two keys alone,
while each brief defines its own output: `drift` (Doc4, Doc5), `stale` and
`missing` (Doc1, Doc2), a `findings` object (T1, T2 and the A questions).
The listers shipped in `c10a5cc`, the T listers in `9da7cc3` and the A
listers in `73df3f4`; their tests ran `check` on A4-shaped output only.

Fix direction: give each registered question its result shape (the keys
its brief names), have `parse_result` and `read_run_verdicts` validate and
store those keys, and add a test per registered question that runs `check`
and `merge` on a line in its brief's shape. It changes the verdict contract
of the repeatable-phase-b spec, which names A4's keys, so it goes through
that spec, or the three listed-question specs, first.

Spec: `agents/specs/repeatable-phase-b/spec.md`, amendment 1.2 (one `findings` object for every question, chosen by the operator on 2026-11-21); tasks: `agents/tasks/repeatable-phase-b/tasks-2.md`.

Done: 2026-11-21 - amendment 1.2 of agents/specs/repeatable-phase-b/spec.md, agents/tasks/repeatable-phase-b/tasks-2.md.

## Pilot the documentation listers' batch sizes on a real audit

Found on 2026-11-20 in a review of this file:
`agents/specs/listed-phase-b-documentation-questions/spec.md` (Briefs)
registers batch sizes that were never measured - 24 for Doc4 and Doc5, 12
for Doc1 and Doc2 - and says the operator's first run on a real project is
the pilot, run twice as A4's was, with any threshold it exposes landing as a
brief version bump. No item or task records it, and no run has happened:
the listers shipped the same day in `c10a5cc`.

Cause: the batch sizes were set by estimate when the spec was written,
because no Doc question had been run on the listed path yet.

Fix direction: in the next audit, which waits for the item above, run each
Doc question's batches twice with the same brief and compare the verdicts,
as the A4 pilot did. Change a registered batch size in
`claude/skills/auditme/checks/auditme/phaseb/candidates.py`, or a brief
threshold with a version bump under `claude/skills/auditme/phaseb/briefs/`,
only where the two runs disagree or a batch fails to return. Small here; the
run itself is in another project.

Note, 2026-11-21: the item above cleared on 2026-11-21, and the pilot ran the
same day on one project, outside an audit, with both runs kept out of its
ledger. Two runs of 13 batches each at the registered sizes, same briefs:
every batch returned a line for every candidate. Same flag decision per
candidate: Doc4 132 of 133, Doc5 78 of 80, Doc1 9 of 9 (identical path lists
8 of 9), Doc2 17 of 17; 236 of 239 overall. So the batch sizes need no
change. Every disagreement traces to a threshold the reviewers themselves
named as unsettled, which lands as a brief version bump:

- Doc4: whether a fix table dated in the spec ("as classified on
  <date>") is a dated record when the names in it have since changed;
- Doc5: whether an example of printed output that leaves out a line is
  drift or an omission, and whether an `(unresolved)` candidate's other
  statements are judged, not only its tokens;
- Doc5: whether a list of values written out in prose (an `exit_reason`
  list) presents itself as complete;
- Doc1: whether a path the section itself calls ignored, and so absent from
  the tracked tree, is stale.

Merging the pilot's verdicts waits for the `phaseb.py check` item above.

Done: 2026-11-21 - pilot run on one project on 2026-11-21 (batch sizes unchanged); the four thresholds it exposed settled by the operator and written into the Doc4, Doc5 and Doc1 briefs at version 3, with `test_doc_brief_settles_the_pilot_thresholds` in `claude/skills/auditme/tests/phaseb/test_briefs.py` and a note in `agents/specs/listed-phase-b-documentation-questions/spec.md` (version 1.2).

## The Stop hook passes silently when the installed checker is missing

Found on 2026-11-21 in the survey made before the checker moved out of the
agents repository, and confirmed the same day with a probe: in a git
repository whose `.pre-commit-config.yaml` lists `id: auditme-changed`, with
a `HOME` that has no `~/.claude/skills/auditme`, `claude/hooks/auditme-stop.sh`
exits 0 with no output, and `python3 -I` on the missing `changed.py` exits 2.
So a reinstall that leaves `~/.claude/skills/auditme` missing or dangling (a
link into a repository that no longer holds the skill, as the move did until
auditor's installer ran) turns the end-of-session audit off without a word.

Cause: `claude/hooks/auditme-stop.sh` runs
`python3 -I "$HOME/.claude/skills/auditme/checks/changed.py"` and blocks only
when its status is 1; any other status falls through to `exit 0`. `changed.py`
itself exits only 0 or 1 (an uncaught exception also exits 1, which blocks),
so the silent statuses are the ones where the checker never ran: 2 for a
missing file, 127 for no `python3`. The project-setup spec's Stop hook section
says only "on exit 1 it prints the Claude Code block decision", so nothing
specifies the other statuses.

Fix direction: small. Before running the checker, block once with a reason
naming the missing path and the install command (`bin/install-claude.py` in
this repository) when `changed.py` is not a file; and block, carrying the
output, on any status other than 0 and 1. Add cases to `tests/test_stop_hook.py`
beside the existing ones: a missing checker, a dangling link, and a stub
exiting 2, each giving one block decision; a stub exiting 0 still gives none.
Update the Stop hook bullet in `agents/specs/project-setup/spec.md` and the
Stop hook section of `docs/reference/cli.md` in the same change.

Done: 2026-11-21 - `claude/hooks/auditme-stop.sh` blocks on a missing or dangling checker and on any status other than 0 and 1; four new cases in `tests/test_stop_hook.py`; amendment 1.6 of `agents/specs/project-setup/spec.md`; the Stop hook section of `docs/reference/cli.md`.

## The project-setup spec still names the agents repository's pin, deploy key and rule paths

Found on 2026-11-21 in a review of this file, checking the records the move
out of the agents repository brought here. `agents/specs/project-setup/spec.md`
(version 1.5, status implemented) still gives the hook block as
`repo: git@github.com:bnomis/agents.git` (line 366), the upgrade command as
`pre-commit autoupdate --repo git@github.com:bnomis/agents.git` (line 376), the
CI secret as `AGENTS_DEPLOY_KEY` with the `github-agents` host alias and its
`insteadOf` rewrite (lines 390-398), and the deploy-key steps against
`--repo bnomis/agents` (lines 459-461). It also cites
`claude/rules/git-conventions.md` (line 168) and `claude/rules/rule-scope.md`
(line 478) as paths in this repository; both are in the agents repository.

Cause: `5a8eb69` (pin auditor, not agents) moved
`claude/skills/project-setup/SKILL.md` and its templates to
`git@github.com:bnomis/auditor.git`, `{{AUDITOR_REV}}`, `AUDITOR_DEPLOY_KEY`
and `github-auditor`, and did not touch the spec. So the spec contradicts the
templates it specifies, and the spec-drift check and the Doc4 question read it
as implemented.

Fix direction: small. A version 1.6 amendment to
`agents/specs/project-setup/spec.md` that matches the hook block, upgrade
command, secret, alias and deploy-key steps to the templates, and names the
two rules as the agents repository's. If the Stop hook item lands first or at the
same time, its Stop hook bullet can go in the same amendment. Leave the dated
task lists (`agents/tasks/project-setup/`) unchanged: they are records.

Note 2026-11-21: the Stop hook item shipped as version 1.6 of the spec (now
in `DONE.md`), so this amendment is version 1.7. Since 1.6 the lines cited
above are at 373 (hook block), 382-383 (upgrade command), 397-405 (secret,
alias and rewrite), 470-472 (deploy-key steps), 173 (`git-conventions.md`)
and 489 (`rule-scope.md`).

Done: 2026-11-21 - amendment 1.7 of `agents/specs/project-setup/spec.md`: the hook block, upgrade command, `AUDITOR_DEPLOY_KEY` secret, `github-auditor` alias and deploy-key steps now match `claude/skills/project-setup/templates/`, and the two cited rules are named as the agents repository's.

## A project with no audit root skips the project-level checks

Found on 2026-10-31 in `agents/specs/project-setup/spec.md`, amendment 1.2,
which records it as a known limit not fixed there. When a project has no
package under `src/` and no extra root, `audit.py` runs no pass, so the
per-root project-level checks (the lockfile, `AGENTS.md`, spec drift) never
run, and a project with no Python passes them without being checked.

Cause: the project-level checks run inside the per-root loop in `main()` of
`claude/skills/auditme/checks/audit.py`, once per root with duplicates
suppressed. With no root, they never run.

Fix direction: deferred until a project without Python adopts the guards.
Then run the project-level checks once when no root exists, which changes the
driver's contract, so it goes through the spec first.

Done: 2026-11-21 - brought forward from its deferral at the operator's request. `PROJECT_CHECKS` in `claude/skills/auditme/checks/auditme/registry.py` (`check_lockfile`, `check_ruff_version`) runs once in `main()` of `claude/skills/auditme/checks/audit.py` when there is no root; tests in `claude/skills/auditme/tests/test_driver.py`; amendment 1.8 of `agents/specs/project-setup/spec.md`; `docs/reference/cli.md` and `docs/setup.md`. Checked on a test project with no Python, which now reports `lockfile-drift` and `ruff-version-drift`.

## The audit reads none of this repository's own Python

Found on 2026-11-21 when `/auditme` was run on this repository. `audit.py`
with no options printed `audit.py: no package under src/ and no extra root;
running the project-level checks only` and emitted no hits. All of this
repository's Python lives under `claude/skills/`: the checker's scripts and
its `auditme` package in `claude/skills/auditme/checks/`, and the tests in
`claude/skills/auditme/tests/`, `claude/skills/auditme-project-setup/tests/`
and `tests/`. Since the installer became `bin/install-claude.sh`, `bin/` holds
no Python. Run by hand with those four directories as `--extra-root`, the
sweep gave 659 hits on 2026-11-21, 654 of them unaccepted; the largest rules
were `literal-duplication` (153), `leading-underscore-def-class` (109),
`leading-underscore-attribute-access` (101), `from-import` (53),
`leading-underscore-const-upper` (49) and `silent-broad-except` (37).
`phaseb.py plan` found no candidates for A1, A4 or T1 the same day; the Doc
questions did have candidates. The commit and push hooks run the same default
sweep, so none of this code has been gated here. The operator chose on
2026-11-21 to stop review-1 of this repository until this is fixed.

Cause: the roots are fixed by layout. `_audit_roots()` in
`claude/skills/auditme/checks/auditme/core.py` takes each package under
`src/` and each `EXTRA_ROOT_NAMES` directory, which is `('bin',)`
(`core.py:146`); `audit.py --extra-root` replaces that set for one run only.
`sweep()` in `claude/skills/auditme/checks/changed.py` runs
`audit.py <repo-root>` with no options, and `phaseb.py`'s listers walk the
same roots, so neither the hooks nor Phase B can be pointed elsewhere. Passing
`claude/skills/auditme/checks` as a root would also name its modules
`checks.auditme.*`, while the checker imports them as `auditme.*`
(`module_dotted` in `core.py` builds names from the root's own name), so the
import-graph and public-surface checks may report false hits on it.

Fix direction: let a project declare its audit roots in one place that
`audit.py`, `changed.py` and `phaseb.py` all read, so the hooks cover the
same code as an audit, with each root's module-name base (here, the directory
the checker puts on `sys.path`). It changes the driver's contract and the
published hooks, so it goes through the project-setup spec
(`agents/specs/project-setup/spec.md`) first. Then land fixes or accept
markers for the catch-up surface before the first real audit of this
repository.

Spec: `agents/specs/project-setup/spec.md`, amendment 1.11; tasks: `agents/tasks/project-setup/tasks-4.md`, then `agents/tasks/project-setup/tasks-5.md`.

Done: 2026-11-21 - amendment 1.11 of `agents/specs/project-setup/spec.md`, `agents/tasks/project-setup/tasks-4.md` and `tasks-5.md`; the backlog is filed as "Fix or accept this repository's audit backlog".

## A worktree's ruff-version-drift hit is hidden by an accept marker

Found on 2026-11-21 in a review of this file. `4641cca` (Task 1 of
`agents/tasks/project-setup/tasks-5.md`, run by a queue in a worktree) added
`# auditme: accept[ruff-version-drift] the ruff installed on PATH is newer
than the 14-day exclude-newer window lets uv.lock pin` above `rev: v0.17.2`
in `.pre-commit-config.yaml` (line 4), to get its commit past the
`auditme-changed` hook. In the main checkout the same day there was no drift
to accept: `.venv/bin/ruff` is 0.17.2, `uv.lock` locks ruff 0.17.2, and
`python3 claude/skills/auditme/checks/audit.py .` gave no
`ruff-version-drift` hit. The ruff on `PATH` was 0.17.6.

Cause: the worktree had no `.venv`, so `ruff_executable()` in
`claude/skills/auditme/checks/auditme/rules/project_hygiene.py` fell back to
the ruff on `PATH`, as it is specified to (amendment 1.5 of
`agents/specs/project-setup/spec.md`). The hit was real for that worktree
and not for the repository, and the marker now accepts any later drift on
that line, in every checkout.

Fix direction: small. Remove the marker. For a run in a worktree, make the
pinned ruff the one the audit finds - a `uv sync` in the worktree before its
first commit - rather than accepting the drift; where that is done (the queue
runner that creates the worktree) is another repository's change, so record
it there, not here.

Done: 2026-11-21 - the marker removed from `.pre-commit-config.yaml`; `audit.py .` in the main checkout gives no `ruff-version-drift` hit, since `.venv/bin/ruff` is 0.17.2. Giving a queue's worktree the pinned ruff is the queue runner's change, in its own repository.

## Ship or reject the three open checker requests

Found on 2026-11-21 in a review of this file. `dfc34b2` filed three entries
under `## Open` in `claude/skills/auditme/requests.md`, each raised by an
audit the same day: "A user guide's parameter list is checked by nothing",
"Listed briefs leave thresholds open that reviewers settle differently" and
"D2 has no carve-out for type-stub packages and notebook kernels".

Cause: the auditme skill (step 3, Mechanical sweep) lets no audit start while
`## Open` has an entry, so these stand between the backlog item below and
the first audit of this repository, and no item recorded them.

Fix direction: for each entry, ship it (the check, brief threshold or
predicate text, its tests, and the catch-up it exposes) or move it to
`## Rejected` with the reason. The first entry adds or widens a check, so it
goes through a spec first; the other two change brief and predicate text,
each with a brief version bump where a brief changes. Do this before the
backlog below, so the backlog's catch-up includes any new check's hits.

Done: 2026-11-21 - all three shipped as `agents/reviews/checker-requests-2026-11-21.md` decided (every recommendation accepted): the T1 (version 2), A4 (4), Doc4 (4) and Doc5 (4) briefs' Thresholds; the T1 lister's `test_files` counting package re-exports (`checks/auditme/phaseb/testmap.py`, amendment 1.3 of `agents/specs/listed-phase-b-test-questions/spec.md`); D2's carve-out in `claude/skills/auditme/SKILL.md`; `requests.md`'s `## Open` emptied.

## Fix or accept this repository's audit backlog

Found on 2026-11-21 when `pyproject.toml` first declared this repository's
audit roots (amendment 1.11 of `agents/specs/project-setup/spec.md`).
`python3 claude/skills/auditme/checks/audit.py .` gave 691 hits, 686 of them
unaccepted. By rule: `literal-duplication` (155),
`leading-underscore-attribute-access` (116), `leading-underscore-def-class`
(111), `from-import` (53), `leading-underscore-const-upper` (49),
`silent-broad-except` (37), `except-interpolation` (30),
`filesystem-envelope-gap` (23), `non-alphabetical-literal` (18),
`leading-underscore-binding` (15), and the remaining rules, each with 8 hits or fewer.
`phaseb.py plan . --question A4` plans 37 candidates in one batch.

Cause: the checker's own code was never swept; the roots were fixed by layout
until the declaration landed, so the hooks gated none of it. Until the
backlog is cleared, `auditme-all` in `.pre-commit-config.yaml` runs at the
`manual` stage only, so a push is not blocked by it; `auditme-changed` still
gates every commit's changed files.

Fix direction: fix or accept every hit, then put `pre-push` back on
`auditme-all` (`stages: [manual, pre-push]`) and run the first audit of this
repository.

Note 2026-11-21: until this is done, every commit that changes a checker file
is blocked by `auditme-changed` on the backlog hits already in that file (and
in files a `literal-duplication` hit relates to it), whether or not the
commit adds any. The commit that shipped the three checker requests added no
hit (685 unaccepted before and after) and was made with
`SKIP=auditme-changed`, as the operator chose; the next checker change meets
the same block.

Review: `agents/reviews/audit-backlog-2026-11-21.md` (answered 2026-11-21); tasks: `agents/tasks/reviews/tasks-1.md`.

Done: 2026-11-21 - agents/reviews/audit-backlog-2026-11-21.md and agents/tasks/reviews/tasks-1.md; the sweep reports no unaccepted hit, and both gates are back on.

## The Stop hook checks an auditor worktree with the main checkout's checker

Found on 2026-11-21 during the `agents/tasks/reviews/tasks-1.md` queue, which
ran in the worktree `.claude/worktrees/reviews-tasks-1`. After Tasks 4 to 9
changed the checker on that branch, the Stop hook kept blocking every turn
with hits the branch's own checker no longer reported: for example
`literal-duplication` on expected values inside `assert` (cleared by R2 of
`agents/reviews/audit-backlog-2026-11-21.md`). At 17:35 UTC
`python3 claude/skills/auditme/checks/audit.py .` in the worktree reported 0
unaccepted hits while the hook still listed well over a hundred. The hook
stopped only once the branch merged into `main` (`52b4813`).

Cause: `claude/hooks/auditme-stop.sh:22` always runs
`$HOME/.claude/skills/auditme/checks/changed.py`, which
`bin/install-claude.sh` links into the main checkout. Its comment gives the
reason ("the installed checker, not the project's pinned one: this is the
early warning"), which holds for a project that only uses the checker. In
this repository the checker under change is the project's own code, so a
branch is judged by the checker it is replacing.

Fix direction: small. When the project root holds its own
`claude/skills/auditme/checks/changed.py` (this repository, or a worktree of
it), the hook runs that one instead; other projects keep the installed
checker. Add a test to `tests/test_stop_hook.py` for both cases.

Done: 2026-11-21 - `claude/hooks/auditme-stop.sh` runs a worktree's own `claude/skills/auditme/checks/changed.py` when it shares its git directory with the checkout the installed checker links into, and never another repository's copy; tests in `tests/test_stop_hook.py`; amendment 1.12 of `agents/specs/project-setup/spec.md`; `docs/setup.md`.

## A second accept marker on one line is silently ignored

Found on 2026-11-21 by Task 14 of `agents/tasks/reviews/tasks-1.md`: the
docstring line `claude/skills/auditme/checks/auditme/rules/state_and_effects.py:1029`
carried `# auditme: accept[leading-underscore-self] ...` followed by
`# auditme: accept[leading-underscore-attribute-access] ...`, and the sweep
still reported `leading-underscore-attribute-access` there as unaccepted
(recorded in that task's Notes; the line was later reworded and both markers
dropped in `57b7a4a`).

Cause: `ACCEPT_COMMENT_RE` in `claude/skills/auditme/checks/auditme/core.py:20`
is `#\s*auditme:\s*accept\b(?:\[([a-z0-9-]+)\])?\s*(.*)$`, matched once per
line. The reason group `(.*)$` swallows any later marker, so only the first
rule named on a line is accepted. Checked the same day:
`accept[rule-a] reason a  # auditme: accept[rule-b] reason b` parses as rule
`rule-a` with reason `reason a  # auditme: accept[rule-b] reason b`.

Fix direction: small, a skill change made between audits. Either parse every
marker on a line (the reason ends at the next `# auditme:`), or report a
second marker on one line as its own hit so it cannot pass unnoticed;
document the choice in `SKILL.md`'s acceptance mechanism, with a test in
`claude/skills/auditme/tests/test_core.py`.

Done: 2026-11-21 - `ACCEPT_COMMENT_RE` in `claude/skills/auditme/checks/auditme/core.py` ends a reason at the next marker and `accept_reason` reads every marker on a line; tests in `claude/skills/auditme/tests/test_core.py`; the acceptance mechanism in `claude/skills/auditme/SKILL.md` and `docs/guide/checker.md`.
