# ADR-0002 — Nothing enters the skill unless a run without it fails a check

**Status:** Accepted (2026-11-10)

## Context

The first deckwright grew a large skill, a helper script and three evidence gates.
A later thread built a good Brawl deck from bare prompts with no skill at all.
The bare model already knows Magic well; what it may lack is the sequence, the
deck's own criteria and the page.

## Decision

Runs without the skill come first, with a one-line prompt, on Opus 5.5. The
outcome checks they fail are the list of what the skill must fix. A check the bare
model passes gets no words in the skill, and each part of the skill stays only if
it turns a failing check into a passing one. Nothing from the design goes into the
skill text because it was agreed in the design; the design says what Deckwright
must do and the checks test it. No script ships unless a check fails without one,
and no bulk card file unless a run without one fails a check.

Rejected: writing the skill from the design and then testing it, because it
produces text the model did not need and cannot show which part earns its place.

## Consequences

The skill may end up very small: the page template, the shape of `deck.json` and
the ledger, and the few rules the bare model broke. Every addition needs a failing
run first, which costs runs. Results state their number of runs and their cost,
and with few runs say "no failure seen in three runs", never "passes".
