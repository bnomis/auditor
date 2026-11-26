"""Helpers that find a project's documents, for rules to share."""

import auditor.hygiene

CLASS_LINE_RE = auditor.hygiene.CLASS_LINE_RE  # auditme: accept[reexport-in-non-init] the API publishes the runner helper under this name
DEF_LINE_RE = auditor.hygiene.DEF_LINE_RE  # auditme: accept[reexport-in-non-init] the API publishes the runner helper under this name
SPEC_SKIP_PARTS = auditor.hygiene.SPEC_SKIP_PARTS  # auditme: accept[reexport-in-non-init] the API publishes the runner helper under this name
spec_markdown_files = auditor.hygiene.spec_markdown_files  # auditme: accept[reexport-in-non-init] the API publishes the runner helper under this name

__all__ = ['CLASS_LINE_RE', 'DEF_LINE_RE', 'SPEC_SKIP_PARTS', 'spec_markdown_files']
