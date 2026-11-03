# 0005 — Patch the mis-cased `$ref`s in the vendored v3.0 schemas

**Status:** Accepted
**Decided:** 2026-11-03

## Context

Eight `$ref` targets in `src/dcatus_validator/schemas/dcat3/` named files that
do not exist on disk, differing only in case — `./Datasetseries.json` against
the real `DatasetSeries.json`, and the same for `AccessRestriction`,
`CatalogRecord`, `ConceptScheme`, `CUIRestriction`, `DataService`,
`QualityMeasurement`, and `UseRestriction`. Lookups are case-sensitive, so
these raised `referencing.exceptions.Unresolvable` — a hard crash, not a
validation failure. Confirmed by direct probe on `datasetSeries`, `record`,
`service`, `themeTaxonomy`, `accessRestriction`, `useRestriction`,
`cuiRestriction`, `hasQualityMeasurement`, and `distribution.accessService`.

The cause is local, not upstream. Checked against
[GSA's schemas](https://github.com/GSA/dcat-us/tree/main/jsonschema/definitions)
on 2026-11-03: they use absolute lowercase refs with no extension
(`/dcat-us/3.0.0/definitions/datasetseries`) that match each file's `$id` and
resolve correctly; filenames are PascalCase and identical to ours. The
`./Xxx.json` form exists only in this repo, where vendoring rewrote those
refs to relative filenames by capitalizing the first letter of the slug.
Single-word names survive that (`agent` → `Agent`); multi-word names lose
their internal capitals.

No NASA catalog populates the affected fields, which is why this never
surfaced. Commit `059aa85` ("readme updates") had already corrected the one
case NASA data hits, `PeriodOfTime`.

## Decision

Correct the 20 `$ref` strings in place across the 7 affected files. Filenames
and all other content are untouched.

An alias shim in `_reference_aliases()` was tested and also works, but was
rejected as indirection — a reader of `Catalog.json` would see a ref that
looks wrong and have to find the shim to learn why it resolves.

## Consequences

- The affected paths now validate instead of crashing, enforcing fields like
  `restrictionStatus` and `cuiBannerMarking` for the first time. Catalogs
  using them may surface errors that validation previously never reached.
- A re-sync must redo the absolute → relative rewrite, preserving the on-disk
  PascalCase. Registering schemas under their upstream absolute paths would
  remove the rewrite step and this whole class of bug — a larger change than
  this fix warranted, but the better long-term fix.
