# 0007 — Federal-only v1.1 fields: map one, pass four through

**Status:** Accepted
**Decided:** 2026-11-05

## Context

A field-by-field audit against the
[migration guide](https://resources.data.gov/resources/dcat-us-3-migration/)
and GSA's reference converter found the pipeline already matched GSA
everywhere except `isPartOf` (ADR-0006) and five federal-only fields:

| v1.1 field | GSA guidance | GSA's converter | This repo |
| --- | --- | --- | --- |
| `primaryITInvestmentUII` | "Can be preserved in `otherIdentifier` if needed" | Passes through | **Maps it** |
| `dataQuality` | "Use `hasQualityMeasurement`" | Passes through | Passes through |
| `systemOfRecords` | SORN URL in `accessRights`/`rights` | Passes through | Passes through |
| `bureauCode` | "will not reject this if included" | Passes through | Passes through |
| `programCode` | "will not reject this if included" | Passes through | Passes through |

## Decision

**Map `primaryITInvestmentUII` to `otherIdentifier`.** This is the one clean
case: `Identifier.json`'s top-level `anyOf` accepts a bare string, so the UII
maps across with no object construction and no invented data. The transform
appends to any existing `otherIdentifier`, matching `transform_references()`.

The reverse is a heuristic, not an inversion. `otherIdentifier` holds
identifiers of every kind and records nothing about their origin, so
`reverse_transform_primary_it_investment_uii()` recovers the first entry
matching v1.1's own pattern (`[0-9]{3}-[0-9]{9}`, from
`schemas/dcat1/dataset.json`) and leaves the rest. An entry matching by
coincidence will be misattributed.

**Leave `dataQuality` and `systemOfRecords` alone.** These are
underdetermined rather than merely unimplemented, which is why GSA's own
converter skips them despite its prose naming a target. `dataQuality` is a
boolean, while `QualityMeasurement` requires an `isMeasurementOf` pointing at
a `Metric` — there is none, and inventing one fabricates provenance.
`systemOfRecords` is a SORN URL: writing it to `accessRights` collides with
the value `transform_access_rights()` derives from `accessLevel` (ADR-0003),
and writing it to `rights` merges it into statements that
`reverse_transform_rights()` joins with `"; "` and cannot split back apart.

**Leave `bureauCode` and `programCode` alone.** GSA explicitly tolerates
them, and its converter passes them through.

## Consequences

- The four pass-through fields land in v3.0 output as undefined properties,
  valid only because no schema sets `additionalProperties: false` — the same
  allowance ADR-0006 relies on.
- Round-tripping a UII is reliable for data this pipeline produced, since the
  forward transform is the only thing writing a UII-shaped string into
  `otherIdentifier`. For third-party v3.0 input it is a guess.
- If GSA later implements `dataQuality` or `systemOfRecords`, that is the
  signal to supersede this ADR rather than guess ahead of it.
