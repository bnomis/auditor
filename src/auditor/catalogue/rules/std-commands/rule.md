## Commands

- Add: `uv add <package>` (runtime dep)
- Add dev: `uv add --dev <package>` (test/lint/build tools)
- Add to optional group: `uv add --optional <group> <package>`
- Remove: `uv remove <package>`
- Upgrade one: `uv lock --upgrade-package <package>`
- Sync the venv to the lockfile: `uv sync`

Do not run `pip install` - it bypasses the lockfile and produces an
inconsistent venv.
