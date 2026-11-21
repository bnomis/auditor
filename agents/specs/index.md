# Spec Index

| Spec | Path | Description |
|------|------|-------------|
| [Project setup](project-setup/spec.md) | `claude/skills/auditme/checks/changed.py`, `claude/skills/auditme/checks/audit.py`, `.pre-commit-hooks.yaml`, `claude/hooks/auditme-stop.sh`, `claude/skills/project-setup/` | Shared audit guards as pinned pre-commit hooks, a global Stop hook, the `/project-setup` skill and its user guide |
| [Auditme false positives](auditme-false-positives/spec.md) | `claude/skills/auditme/checks/auditme/rules/` | Narrows raises-section-drift, missing-raises-section, passthrough-shim and non-alphabetical-literal where they report hits the code does not have |
| [Repeatable Phase B](repeatable-phase-b/spec.md) | `claude/skills/auditme/checks/auditme/phaseb/`, `claude/skills/auditme/checks/phaseb.py`, `claude/skills/auditme/phaseb/briefs/` | Listed candidates, versioned briefs, batch checks and a hash-keyed verdict ledger, so a Phase B question gives the same answer twice; A4 first |
| [Raises section resolution](raises-section-resolution/spec.md) | `claude/skills/auditme/checks/auditme/rules/error_handling.py` | Widens raises-section-drift to follow callees with no `Raises:` section and `Class.method()` calls |
| [Listed Phase B documentation questions](listed-phase-b-documentation-questions/spec.md) | `claude/skills/auditme/checks/auditme/phaseb/docrefs.py`, `claude/skills/auditme/phaseb/briefs/` | Puts Doc4, Doc5, Doc1 and Doc2 on the listed Phase B path, and sets the cadence for sampled questions |
| [Listed Phase B test questions](listed-phase-b-test-questions/spec.md) | `claude/skills/auditme/checks/auditme/phaseb/testmap.py`, `claude/skills/auditme/phaseb/briefs/` | Puts T1 and T2 on the listed Phase B path, with the related test files in each hash |
| [Listed Phase B architecture questions](listed-phase-b-architecture-questions/spec.md) | `claude/skills/auditme/checks/auditme/phaseb/architecture.py`, `claude/skills/auditme/phaseb/briefs/` | Puts A11, A19, A1 and A17 on the listed Phase B path, reusing the sweep rules' site finders |
