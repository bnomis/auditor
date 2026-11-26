"""Point every test at the default rule catalogue, and register its Phase B questions.

The runner holds no rules: it loads the repository `AUDITOR_RULES_PATH` names.
A test that needs the variable unset deletes it with `monkeypatch`.
"""

import os
import pathlib

import auditor.phaseb.candidates

CATALOGUE = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'auditor' / 'catalogue'

os.environ['AUDITOR_RULES_PATH'] = str(CATALOGUE)
auditor.phaseb.candidates.use_rules_repository()
