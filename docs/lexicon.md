# Lexicon

The words someone needs defined to talk about using or developing Deckwright. A
term earns an entry only if it is language rather than code, needs defining, and
is the one word for its concept (the design:lexicon tests). Admitted in the
milestone 1 design interview, 2026-11-10; *scene* and *why* in the deck page
design interview, 2026-11-11; *crossover*, *ladder*, *on offer*, *packed file* and
*round* in the Arena close-out, 2026-11-13.

**category** — A job that cards in the deck do, such as ramp or removal. Each card
sits in exactly one. Distinct from a *tag*, of which a card may have several, and
from a creature type, which is a *criterion*. Not used for a category: stack, package, pack. See
[ADR-0005](adr/0005-a-category-is-a-job-and-a-creature-type-is-a-criterion.md).

**criterion** — Something the player said the deck must be: the format, a
creature type, a colour pair, a set limit. Distinct from a *category*.

**crossover** — A printing that carries another franchise's world and characters
into Magic, often under a name of its own printed on Arena. It belongs to a
printing, not to a card: the same card may also have printings that are not
crossover.

**finding** — One thing the review reports: a fact from Scryfall plus Deckwright's
judgement with a reason.

**ladder** — The three steps a *round* shows for a creature-type *criterion*: cards
of the type that do the job, cards that reward the type and do the job, and the
strongest cards for the job. See
[ADR-0012](adr/0012-a-round-shows-every-step-of-the-ladder.md).

**ledger** — The deck's history: every card in, card out, *criteria* change,
*category* change, dismissed *finding*, and the deck's name with its folder's rename, each with a reason, only ever added to. Distinct from the deck's current state.
Not used: change log. See [ADR-0011](adr/0011-a-save-writes-the-deck-folder-and-the-page-is-shown-as-one-packed-file.md).

**maybeboard** — Cards not in the deck that might go in: ones the player saved for
later, and Deckwright's swap suggestions.

**on offer** — Said of cards put before the player to choose from and not yet
decided: in neither the deck nor the *maybeboard*. See
[ADR-0013](adr/0013-the-deck-page-shows-the-cards-on-offer.md).

**packed file** — The deck page as one file holding the deck folder's text and
pictures, which the player opens to see the deck. A copy made from the folder,
never the deck itself. See
[ADR-0011](adr/0011-a-save-writes-the-deck-folder-and-the-page-is-shown-as-one-packed-file.md).

**place** — Room for one copy of a card in a *category*. Not used: slot.

**round** — One set of about ten cards *on offer* for a *category*, which the
player picks from before the next is shown. Distinct from a whole *category*,
which may take several rounds. See
[ADR-0012](adr/0012-a-round-shows-every-step-of-the-ladder.md).

**scene** — A short looping play of one thing the deck does, shown step by step
with the deck's own cards. See
[ADR-0008](adr/0008-scenes-are-played-from-data-with-whole-card-pictures.md).

**tag** — Any job a card does, used for counting. A card has one *category* and may
have several tags.

**template** — The starting shape of a deck: how many *categories* and how many
*places* in each. Not the page layout.

**why** — The one sentence saved with a card saying what it does for this deck.
Distinct from the *ledger*'s reason, which says why a decision was taken.

Proposed, not yet admitted: *shortlist*, *approved*.
