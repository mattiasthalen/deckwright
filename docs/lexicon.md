# Lexicon

The words someone needs defined to talk about using or developing Deckwright. A
term earns an entry only if it is language rather than code, needs defining, and
is the one word for its concept (the design:lexicon tests). Admitted in the
milestone 1 design interview, 2026-11-10; *scene* and *why* in the deck page
design interview, 2026-11-11.

**category** — A job that cards in the deck do, such as ramp or removal. Each card
sits in exactly one. Distinct from a *tag*, of which a card may have several, and
from a creature type, which is a *criterion*. Not used: stack, package, pack. See
[ADR-0005](adr/0005-a-category-is-a-job-and-a-creature-type-is-a-criterion.md).

**criterion** — Something the player said the deck must be: the format, a
creature type, a colour pair, a set limit. Distinct from a *category*.

**finding** — One thing the review reports: a fact from Scryfall plus Deckwright's
judgement with a reason.

**ledger** — The deck's history: every card in, card out, *criteria* change,
*category* change and dismissed *finding*, each with a reason, only ever added to. Distinct from the deck's current state.
Not used: change log. See [ADR-0010](adr/0010-a-deck-is-a-folder-of-plain-files-with-its-hero-art-and-tokens.md).

**maybeboard** — Cards not in the deck that might go in: ones the player saved for
later, and Deckwright's swap suggestions.

**place** — Room for one copy of a card in a *category*. Not used: slot.

**scene** — A short looping play of one thing the deck does, shown step by step
with the deck's own cards. See
[ADR-0008](adr/0008-scenes-are-played-from-data-with-whole-card-pictures.md).

**tag** — Any job a card does, used for counting. A card has one *category* and may
have several tags.

**template** — The starting shape of a deck: how many *categories* and how many
*places* in each. Not the page layout.

**why** — The one sentence saved with a card saying what it does for this deck.
Distinct from the *ledger*'s reason, which says why a decision was taken.

Proposed, not yet admitted: *shortlist*, *round*, *ladder*, *approved*.
