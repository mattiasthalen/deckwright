# ADR-0013 — The deck page shows the cards on offer

**Status:** Accepted (2026-11-12) · **Supersedes:** [ADR-0009](0009-the-deck-page-is-one-night-page-in-the-decks-colours.md)

## Context

ADR-0009 decided the deck page's look: one night page read top to bottom, in the
deck's colours, with `index.html` as the statement of the look and a browser test
that fails when a part is missing. It rejected night and gold for every deck,
tabs, a light version, and describing the look in the skill text.

A round's cards have to be readable as cards when they are offered. In a project
thread, card pictures attached one by one show as small file tiles, links to
Scryfall were reported as unusable, and a message holding an image link is
refused. An attached page opens in the chat (ADR-0011).

## Decision

The page is one page read top to bottom, in this order: a hero with the hero
card's artwork, the deck name, a pitch, the criteria and headline numbers counted
by the page; the cards on offer; the scenes; the cards by category, each opening
a dialog with the card, its cost as symbols, its rules text and its why; the mana
curve split into creatures and other spells; the handbook with a chapter list
that stays in view; the ledger; the Arena list.

The cards on offer are the round the player is choosing from, read from
`deck.json`: each as its whole picture, numbered as in the chat, with its reason,
under its step of the ladder when the round has steps, and marked when Deckwright
suggests it or when it is a crossover card. With nothing on offer the part is not
drawn.

Headings use a display serif and body text a humanist sans. The background is
night for every deck. The accent comes from the colours of the deck's cards: one
colour gives that colour, several give a blend, none gives gold. The curve keeps
two fixed colours, so its two parts stay apart in any deck.

`index.html` is the statement of this look. A browser test opens it with a test
deck and fails when a part above is missing.

Rejected, beside what ADR-0009 rejected:

- One numbered picture sheet per round: the page shows the same cards larger,
  with their reasons, beside the deck they would join.
- A second, smaller page for rounds: a second layout to keep in step.

## Consequences

The player chooses with the page open, and the page changes at every round, not
only at every pick. `deck.json` holds the round on offer, so a deck opened later
shows the last round that was not answered. A change to the look is still a
change to `index.html` and to the browser test together.
