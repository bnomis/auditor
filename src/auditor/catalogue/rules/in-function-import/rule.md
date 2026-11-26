# in-function-import

Flag every import inside a function.

The variant labels the imported module `stdlib`, `first-party` or
`third-party`. Refinement (2026-11-21): a module under a declared root
(`[tool.auditme]`, either mode) is first-party, not only the importer's own
package, so an import between two declared roots is labelled as one.
