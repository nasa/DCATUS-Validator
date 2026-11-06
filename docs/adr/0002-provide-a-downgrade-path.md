# 0002 — Provide a v3.0 → v1.1 downgrade path

**Status:** Accepted
**Decided:** 2026-08-19 (commits `385e456`/`c6fe157`; ADR backfilled 2026-11-03)

## Context

GSA's [migration guide](https://resources.data.gov/resources/dcat-us-3-migration/)
defines only the v1.1 → v3.0 direction; a reverse path is a NASA-original
capability, merged with no PR body explaining the motivation. **The rationale
is not recorded anywhere in the history** — not in the commits, the PR, or the
README. This ADR documents that the decision was made and what it costs; it
does not reconstruct why.

Since v3.0 is strictly richer than v1.1, a downgrade is necessarily lossy.
The collapses the downgrade path makes:

- `temporal`, `spatial`, `conformsTo`: first array element wins, remaining
  elements are dropped.
- `rights`: array joined into one string with `"; "`.
- `accrualPeriodicity`: has no v1.1 field; the mapped duration is written
  into `modified` when `modified` is otherwise absent.
- Fields with no v1.1 equivalent at all are dropped outright.

## Decision

Provide a best-effort, lossy reverse of the upgrade path, accepting the
collapses listed above rather than refusing to downgrade documents that
can't round-trip cleanly.

## Consequences

- A downgrade-then-upgrade round-trip is not guaranteed to reproduce the
  original v3.0 document; information is genuinely lost (truncated arrays,
  joined strings).
- An upgrade-then-downgrade round-trip of an original v1.1 document is the
  intended lossless direction.
- If the real reason for needing this path is ever established, add it here.
  Until then it stays unrecorded rather than guessed at.
