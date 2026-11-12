# ADR-0010 — A deck is a folder of plain files, with its hero art and tokens

**Status:** Superseded by [ADR-0011](0011-a-save-writes-the-deck-folder-and-the-page-is-shown-as-one-packed-file.md) (2026-11-12)

## Context

ADR-0003 decided that each deck is one artifact holding `index.html`, `deck.json`,
`LEDGER.md` and `cards/<scryfall id>.jpg`, with relative paths, and rejected the
deck inside the page file, the artifact database, embedded images, Scryfall image
links and the ledger inside `deck.json`. Its reasons stand: about a hundred saves
per deck, a deck resumed from its link, and pages that cannot load outside images.

The page now opens with the hero card's artwork (ADR-0009) and plays scenes that
show tokens and deal drawn cards in as Magic card backs (ADR-0008). None of these
pictures is in the folder ADR-0003 listed.

## Decision

Each deck is one artifact holding plain files, by relative path:

- `index.html`, the deck page, identical for every deck;
- `deck.json`, the deck as it is now;
- `LEDGER.md`, how it got there, only ever added to;
- `cards/<scryfall id>.jpg`, the picture of each card in the deck and of each
  token a scene uses;
- `art/<scryfall id>.jpg`, the artwork crop of the hero card, which is a card in
  the deck; a two-faced card's crop is on its first face;
- `cards/back.jpg`, Scryfall's picture of the Magic card back, saved when a scene
  draws cards.

A save publishes `deck.json` and the new ledger entry together. The page asks for
nothing outside the folder except its font stylesheet and the fonts it names.

Rejected, beside what ADR-0003 rejected:

- Cutting the hero art out of the saved card picture: about 400 pixels of art
  against the crop's 626, and Scryfall offers nothing wider.

The architecture tests enforce this boundary.

## Consequences

As in ADR-0003: each save is a small publish, the two files can disagree and
Deckwright checks them on opening, and the folder can later move to a repository.
A deck now has one more file to fetch when its hero card is set, one per token,
and the card back when a scene draws cards. A missing art file or token picture
leaves the hero without art or the token as a named blank card, and a missing
card back leaves drawn cards as blank cards.
