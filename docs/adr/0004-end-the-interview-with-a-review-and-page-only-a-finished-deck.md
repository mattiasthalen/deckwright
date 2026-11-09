# ADR-0004 — End the interview with a review, and give the deck page only to a finished deck

**Status:** Accepted (2026-11-09)

## Context

S1 ends the interview when every category is done or the player says stop, and renders
the deck page either way, so a page can show a third of a deck. S4 (#10) asks for a
review that judges the deck and suggests improvements. The owner judges a deck as a
whole, not by its parts, and treats the page as the deck: "no artefact, no deck". Three
evals stop partway and ask for the page. A deck is kept in its own file and can be
picked up in a later conversation where a folder outlives it (A6); in plain chat nothing
does.

## Decision

The interview runs, in one conversation: the categories, then filling the deck to its
template's deck size, then the review, then the improvements, then the deck page. A deck
is finished when it holds the deck size and has been reviewed since its last change to
anything the review judged against (its cards, a category target, the bracket target,
the theme, the plan). Only a finished deck gets the deck page. Stopping keeps the deck
file and renders no page; a page the player asks for before the deck is finished renders
marked unfinished, with its count and whether it was reviewed. Picking up an unfinished
deck carries the interview on; picking up a finished one offers nothing until the player
says what they want.

Rejected:

- The review only when the player asks, after the page: #10 makes it how a build ends.
- The review in a later conversation, carried by the deck file or by the page itself:
  out of v0.1; plain chat keeps nothing, and the page as a carrier is a second deck
  format.
- A page rendered on every stop, as S1 does: a page of a partial deck reads as the deck.
- No page at all before the deck is finished: the player asking for one is the player
  saying what they want, and the existing evals ask for it.
- Removing pick-up of a half-built deck: a full build with a collection read can outlast
  a conversation, and S2 ships it.

## Consequences

The page's finished state is checkable by the script from the deck file alone. Any change
the review judged against makes a finished deck unfinished until it is reviewed again,
so a swap made during the improvements ends in one more review. A conversation must hold
a full build, its review and its improvements (A9). Evals that stop early now check for
the unfinished mark.
