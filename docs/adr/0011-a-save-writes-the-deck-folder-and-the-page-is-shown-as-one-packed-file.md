# ADR-0011 — A save writes the deck folder, and the page is shown as one packed file

**Status:** Accepted (2026-11-12) · **Supersedes:** [ADR-0010](0010-a-deck-is-a-folder-of-plain-files-with-its-hero-art-and-tokens.md)

## Context

ADR-0010 decided that a deck is one artifact holding plain files, and that a save
publishes `deck.json` and the new ledger entry together. In the first real build
(2026-11-11) that broke down: each publish from a shared folder raised an approval
prompt, and the account's limit of 200 published versions a day was used up
before the first pick, so the page was never published during the build. The
build went on by writing the files to disk and attaching the page to the chat as
one file holding its data and pictures. The player can open an attached page in
the chat; attached card pictures show there only as small file tiles.

## Decision

The deck is still a folder of plain files, by relative path: `index.html`,
`deck.json`, `LEDGER.md`, `cards/<scryfall id>.jpg`, `art/<scryfall id>.jpg` and
`cards/back.jpg`, as ADR-0010 listed them. The folder is named
`<format>-<deck name>` in lower case with hyphens, and `<format>-<what the deck is
about>` until the player has named the deck; a name already taken gets a number.

A decision is saved when `deck.json` and `LEDGER.md` are written to the folder.
Saving does not publish.

The player sees the deck as one packed file, attached to the chat: the deck page
with the folder's files inside it, the text files as text and the pictures as
data URLs. A script shipped with the skill packs the folder; it also writes the
deck's name into the page's title. The packed file carries every picture
`deck.json` names (the deck's cards, the maybeboard, the tokens, the hero art,
the card back and the cards on offer) and no picture of a card offered in an
earlier round and not taken. It is enough to open the deck again in a new
conversation.

The folder is published as an artifact only when the player asks for a link, to
the same link each time. A publish that fails is reported and stops nothing.

The page asks for nothing outside the folder, or outside the packed file, except
its font stylesheet and the fonts it names.

Rejected:

- Publishing after every decision (ADR-0010): approval prompts and the daily
  limit, as above.
- Publishing at fixed points of the build: the same limits, met less often, and
  the packed file already shows the deck.
- A packed file holding only the pictures of the cards on offer: about 12 MB
  for a full Brawl deck was judged acceptable, and a page that grows with the
  deck is what the player wants to see.
- Packing by hand in each conversation: the first build improvised it, and each
  build would do it differently.

The architecture tests enforce this boundary.

## Consequences

A build needs no publish at all. A deck that was never published exists as its
folder and its last packed file; if both are lost, so is the deck. The packed
file grows to roughly the size of the deck's pictures and is sent whenever the
page is shown. ADR-0010's rejection of the deck inside the page file still holds
for the saved state: the folder is the deck, and the packed file is a copy made
from it. Renaming the deck renames the folder, and the ledger records it.
