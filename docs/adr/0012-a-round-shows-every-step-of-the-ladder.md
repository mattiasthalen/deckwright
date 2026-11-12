# ADR-0012 — A round shows every step of the ladder

**Status:** Accepted (2026-11-12) · **Supersedes:** [ADR-0006](0006-shortlists-come-from-a-tag-search-and-a-text-search-read-by-judgement.md)

## Context

ADR-0006 decided how a shortlist is found: a Scryfall tag search and a rules-text
search, merged, limited to cards legal in the format and on Arena, read by
judgement. For a creature type it set a ladder of three steps and let the player
decide when to go down a step. In the first real build (2026-11-11) the first
round of a category showed eight Rats for eight places; the player took all
eight, then asked whether the deck would be widened beyond Rats. From the next
category on, every round showed all three steps, and the player picked across
them each time. One of the eight Rats was later cut as the weakest fit.

## Decision

Per category, Deckwright runs a Scryfall tag search and a rules-text search,
merges them, limits both to cards legal in the format and on Arena, and says
which search found what. A job with no tag gets the text search with a warning.
At each step it reads the 175 most played cards and the newest cards, merged,
picks by judgement, and says how it narrowed.

For a creature type, a round shows every step of the ladder together, each under
its own heading: cards of the type that do the job, cards that reward the type
and do the job, and the strongest cards for the job meeting the other criteria.
The round holds about ten cards in all, split by judgement, and states each
step's full count. A further round of one step is shown on the player's word.

Rejected:

- One step at a time, the player deciding when to go down (ADR-0006): the
  player fills the category before seeing the wider steps.
- One step at a time with a reminder that wider steps exist: the same, with a
  sentence added.
- No ladder, every card ranked together: the headings are what show the cost of
  leaving the type.
- A mechanical ranking rule and a bulk card file, as ADR-0006 rejected them.

## Consequences

The player weighs the type against the best cards for the job in every round.
A type with many cards for one job shows only a few of them in the first round;
the stated count says how many were left out. Shortlists still depend on the
model's judgement, so their quality is judged blind rather than counted.
