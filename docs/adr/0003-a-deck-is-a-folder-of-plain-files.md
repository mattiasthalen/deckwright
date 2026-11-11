# ADR-0003 — A deck is a folder of plain files

**Status:** Superseded by [ADR-0010](0010-a-deck-is-a-folder-of-plain-files-with-its-hero-art-and-tokens.md) (2026-11-11)

## Context

The deck page is updated about a hundred times per deck, and a new conversation
must be able to resume the deck from its link. Artifact pages cannot load outside
images (shown by a spike); files published beside `index.html` load.

## Decision

Each deck is one artifact holding plain files: `index.html`, the page template,
identical for every deck; `deck.json`, the deck as it is now; `LEDGER.md`, how it
got there, only ever added to; and `cards/<scryfall id>.jpg`. Paths are relative.
A save publishes `deck.json` and the new ledger entry together.

Rejected:

- The deck inside the page file: the template must stay identical across decks.
- The artifact database: a store with its own API for what two files hold.
- Embedded images: pages of about 4 MB.
- Scryfall image links: blocked by the page's security policy.
- The ledger inside `deck.json`: history and current state are different things.

## Consequences

Each save is a small publish rather than a page rewrite. The two files can
disagree, so Deckwright checks on opening that `deck.json` matches what the ledger
adds up to, and the player settles any difference. Nothing is tied to the artifact
platform beyond publishing files, so the folder can later move to a repository.
