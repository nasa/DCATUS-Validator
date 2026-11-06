# 0006 — Implement v1.1 `isPartOf` as v3.0 `datasetSeries`

**Status:** Accepted
**Decided:** 2026-11-05

## Context

Step 13 of the
[migration guide](https://resources.data.gov/resources/dcat-us-3-migration/)
maps v1.1's dataset-level `isPartOf` onto v3.0's catalog-level
`datasetSeries`. GSA's reference converter implements it; this repo did not,
so `isPartOf` passed through into v3.0 output where it is not defined. This
is forward-looking rather than a live fix: `isPartOf` appears nowhere in the
fixtures, including the 21,743-dataset `dcat3-smd.json`.

One constraint shaped the implementation. GSA sets `series["@id"]` from the
v1.1 `identifier` unconditionally, but `DatasetSeries.@id` declares
`"format": "iri"` and `validate.py` enforces it. Of the 21,743 identifiers
in `dcat3-smd.json`, 10,963 (50.4%) are bare DOIs like `10.26030/y0ng-8r17`,
which fail it — copying GSA verbatim would emit invalid v3.0 for half this
catalog.

## Decision

Implement Step 13 as `transforms.build_dataset_series()`, a catalog-level
pass running after the per-dataset loop — the first of its kind here, since
every other function in `transforms.py` is `(dataset: dict) -> dict` and
promoting a parent needs the whole catalog. Linkage resolves against the
pre-transform identifiers (first occurrence wins on duplicates) while output
is built from the transformed datasets, matching GSA — as does treating a
dataset as a parent iff another's `isPartOf` equals its `identifier`, nesting
children as `seriesMember`, and raising on self-reference or nested series.

Three deliberate divergences from GSA:

- **Non-IRI identifiers do not become `@id`.** An identifier that passes
  `_is_iri()` becomes `@id` and the `identifier` key is dropped, since
  `DatasetSeries` has no such field. One that does not is retained in
  `identifier` instead — emitting it as `@id` would be invalid, and dropping
  it would lose the value the downgrade needs to restore `isPartOf`.
- **Orphans keep `isPartOf`.** Where a child names a parent absent from the
  catalog, GSA strips the field and silently loses the linkage; here the
  dataset stays top-level with a warning naming both.
- **The downgrade reverses it.** `reverse_transform_dataset_series()` expands
  each series back into `dataset[]`, per the house convention that every
  forward transform has a named reverse. It is the only reverse taking a
  catalog, and `datasetSeries` was removed from `V3_ONLY_FIELDS["catalog"]`
  so the drop-list no longer erases it first.

## Consequences

- Ordering is load-bearing both ways: forward, identifiers are snapshotted
  before the loop rebinds them; reverse, expansion precedes the per-dataset
  loop so members receive the rest of the chain.
- `upgrade.py` gains a `dataset_series` count. Promoted parents are not
  Datasets, so without counting them separately `upgrade_successful` would
  read false whenever a series was built.
- Retaining `identifier` on a non-IRI series depends on
  `additionalProperties` staying unset, as orphaned `isPartOf` does. A schema
  sync that closes it makes both invalid.
- A parent lacking `title` or `description` yields invalid v3.0, since both
  are Mandatory on `DatasetSeries` — surfaced in `--strict` rather than
  papered over with invented values.
