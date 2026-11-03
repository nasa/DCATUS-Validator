# 0003 — Keep `accessLevel`/`accessRights` on both conversions

**Status:** Accepted
**Decided:** 2026-11-03 (commit `fc320ba`, reversing `7ed9c24` of 2026-10-22)

## Context

Commit `7ed9c24` made the upgrade delete `accessLevel` after adding
`accessRights`, and the downgrade delete `accessRights` after deriving
`accessLevel`. GSA's
[migration guide](https://resources.data.gov/resources/dcat-us-3-migration/)
Step 5 says the opposite, verbatim: *"Until updated OMB guidance is issued,
keep `accessLevel` in your records — the v3.0 schema will not reject it."*

Downstream GSA tooling accepts either field, so dropping `accessLevel`
would not have broken data.gov ingest outright — as of 2026-11-03,
`datagov-catalog` indexes `accessRights` with `accessLevel` as the fallback,
and its search filter accepts both `access_level` and `accessLevel` as query
parameters. The reason to keep both is the guide's explicit instruction and
the fact that `accessLevel` remains the field published v1.1 consumers know,
not a hard dependency in GSA code.

## Decision

Reverse `7ed9c24`: upgrade adds `accessRights` without removing
`accessLevel`; downgrade derives `accessLevel` without removing
`accessRights`. Both fields are present after either conversion, keeping
round-trips lossless and symmetric for this pair.

## Consequences

- Converted catalogs carry both fields simultaneously, which is redundant but
  matches what GSA currently instructs.
- If OMB later issues updated guidance that retires `accessLevel`, this
  decision needs revisiting — it is explicitly provisional per the guide's
  own wording.
