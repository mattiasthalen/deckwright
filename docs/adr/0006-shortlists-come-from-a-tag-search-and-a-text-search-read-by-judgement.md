# ADR-0006 — Shortlists come from a tag search and a text search, read by judgement

**Status:** Superseded by [ADR-0012](0012-a-round-shows-every-step-of-the-ladder.md) (2026-11-12)

## Context

A category can have over a thousand candidates (1,222 ramp cards for a black-green
Commander deck by Scryfall's tags, 2026-11-10). Scryfall's tags miss cards with
unusual wording, and its popularity rank exists only for Commander.

## Decision

Per category, Deckwright runs a Scryfall tag search and a rules-text search,
merges them, limits both to cards legal in the format and on Arena, and says which
search found what. A job with no tag gets the text search with a warning. For a
creature type there is a ladder: cards of the type that do the job, then cards that
reward the type and do the job, then the strongest cards for the job meeting the
other criteria; the player decides when to go down. At each step Deckwright reads
the 175 most played cards and the newest cards, merged, picks by judgement, and
says how it narrowed.

Rejected: a mechanical ranking rule, because it ignores the deck and teaches
nothing; a bulk card file, because the limit is reading, not fetching.

## Consequences

Shortlists depend on the model's judgement, so their quality is judged blind
rather than counted. What the 175-card read misses is measured, without a pass
mark.
