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

## Addendum 2026-11-12

The first real build with the skill (2026-11-11) failed in eleven ways, filed as
#39 to #49. For those, that build is the failing run: the skill was loaded and
the behaviour was still wrong, so no bare round was run before the skill text
changed. Each fix has a check, and a skill round of the affected briefs is
reported with its number of runs. #46 (terms explained where first used) may be
something a bare run already does; it was accepted as one line that might not
have been needed.

## Addendum 2026-11-13

The first real builds also stand as the failing run for the skill side of #29
(cards named in the chat as Scryfall links and shown as lone pictures, where the
packed file now shows them) and #57 (deck folders named by date, which collide
when two decks are built on one day). The `layout` field of a card's display copy
(#22) is in the skill because the page's Arena list needs it to write each card
under the name Arena imports, not because a run failed without it.

## Addendum 2026-11-13

Whether the tutor should explain evergreen keywords like flying and menace was
settled on a decision card, with three options: explain every keyword, explain
only terms that are not evergreen, or ask the player once. Asking the player once,
in the intent interview, was chosen, so the skill's question comes from that
decision. S9 follows the answer: the question is asked once, and every term is
explained where first used unless the player said no.
