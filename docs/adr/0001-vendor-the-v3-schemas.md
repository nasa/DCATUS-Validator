# 0001 — Vendor the v3.0 schemas as 26 per-class files

**Status:** Accepted
**Decided:** 2026-08-14 (commit `a624e0a`; ADR backfilled 2026-11-03)

## Context

`src/dcatus_validator/schemas/dcat3/` holds 26 separate JSON Schema files
(`Dataset.json`, `Distribution.json`, `Organization.json`, `Document.json`,
etc.), added with no note on upstream version or date. Internal markers —
`_oldDocs` keys, `requirementLevel` annotations, and lowercase `$id` slugs
(e.g. `.../definitions/accessrestriction`) — indicate these were generated
output from a GSA tool rather than transcribed by hand, but the commit
doesn't say which generator, version, or run.

## Decision

Continue vendoring the schemas as static files checked into the repo, split
one class per file and cross-referenced with `$ref`, rather than fetching
from GSA at runtime or inlining a single monolithic schema.

## Consequences

- Validation works offline and is pinned to a known (if undated) snapshot —
  no network dependency, no surprise schema drift mid-run.
- Re-syncing against a newer GSA release is currently guesswork: there is no
  recorded upstream commit, tag, or date to diff against. Whoever vendors an
  update next should record the source and date here or in a successor ADR.
- The generator that produced these files has at least one known bug — see
  [Known Issues](../known-issues.md). One such bug, mis-cased `$ref`s, was
  patched in place by [ADR-0005](0005-patch-miscased-refs-in-vendored-schemas.md),
  so the vendored files are no longer byte-identical to generator output.
