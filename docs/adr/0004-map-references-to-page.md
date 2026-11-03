# 0004 — Map v1.1 `references` to v3.0 `page`

**Status:** Accepted
**Decided:** 2026-11-03 (commit `fc320ba`)

## Context

GSA's [migration guide](https://resources.data.gov/resources/dcat-us-3-migration/)
does not mention `references` anywhere, so upgrading a v1.1 catalog left it
untouched — a field absent from the v3.0 Dataset schema.

Checked both schemas directly:

- [v1.1 `references`](https://resources.data.gov/resources/dcat-us/#references)
  ("Related Documents", array of URL strings, 0..n) — the `describedBy` entry
  confirms intent: a data dictionary belongs in `describedBy`, other
  documentation "belongs in `references`".
- [v3.0 `page`](https://resources.data.gov/standards/catalog/dcat-us-3/dataset/)
  ("List of pages or documents about this dataset", `foaf:page`, range
  `foaf:Document`) describes the same relation.

`isReferencedBy` (`dcterms:isReferencedBy`) is the inverse relation —
resources that cite the dataset, not documents about it — and is the wrong
target despite the name similarity.

## Decision

Map v1.1 `references` to v3.0 `page` as an array of `Document` objects, and
drop the old `references` key after conversion — GSA gave no instruction to
keep it, unlike `accessLevel` (ADR-0003).

`Document` requires a `title` and declares `"format": "iri"` on `accessURL`,
so entries that aren't valid IRIs (including v1.1's `[[REDACTED...]]`
markers) are carried as title-only Documents rather than being dropped or
emitted as invalid IRIs. IRI validity is decided by the same format checker
the validator runs, so the transform cannot disagree with validation.

## Consequences

- This mapping is an inference from the two schemas' own field definitions,
  not sanctioned GSA guidance — if GSA later documents a different mapping,
  this ADR should be superseded.
- Round-tripping a REDACTED marker through upgrade then downgrade recovers
  the original marker string, since the title is preserved even without an
  `accessURL`.
- `page` was previously on the drop-list for downgrade, which would have
  undone the reverse mapping; it was removed from that list as part of this
  change.
