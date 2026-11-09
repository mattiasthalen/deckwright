# Lexicon

A term earns an entry when it is the domain's language rather than the code's, means
something here its ordinary sense does not carry, and is the one word for its concept.

**template** — A format's list of *categories*, each with a *target*, the format's
deck size and its default *bracket target*. A new format is a new template.

**category** — A role a card plays in the deck, such as ramp or card advantage, with a
test for what counts. Distinct from a card's type (creature, instant): one card can
count in several categories, or in none.

**target** — The rough number of cards a *template* asks for in a *category*. Not the
game's sense of targeting something with a spell. The **bracket target** is the other
sense: the power bracket the player aims the deck at, 2 unless they set another.

**tally** — The script's count of a deck against its *template*: each *category* against
its *target*, the total against the deck size, the checks and the bracket. Only a tally
gives a count; nothing is counted by hand.

**interview** — The guided walk through a *template* while the player builds a deck. It
ends with the deck's *review*, the improvements the player chooses, and the deck page.

**review** — deckwright's judgement of a whole deck once it holds the deck size: how it
wins, its curve against its mana, how it fares without its commander, and its
*categories* in that light. Distinct from a *critique*, which judges one card. See
[ADR-0004](adr/0004-end-the-interview-with-a-review-and-page-only-a-finished-deck.md).

**finished** — A deck that holds its *template*'s deck size and has had its *review*
since anything the review judged against last changed. Distinct from full, which only
counts cards. Only a finished deck gets the *deck page*.

**suggestion** — A card deckwright offers for a *category*. Never a choice: only the
player's yes puts a card in the deck.

**critique** — deckwright's judgement of what a card actually does, given its *lookup*,
and whether it earns its place in the *category* the player put it in.

**lookup** — Card facts read from Scryfall during the conversation. Distinct from
recall: nothing is said about a card that did not come from a lookup or from the player.

**deck page** — The styled page a *finished* deck gets. Distinct from the decklist,
the import text it carries.

**maybeboard** — The cards the player is looking out for, each with the card in the deck
it would replace and why. Distinct from the deck: its cards count towards nothing. The
decklist carries it as `// MAYBEBOARD`.

**available** — A copy the player owns that this deck may use. Distinct from owned:
copies in a ManaBox deck start as not available, and the player's own words change
what is.

**theme** — What the player wants the deck built around, in their own words, such as
"Bloomburrow rats". Distinct from the *plan*, which settles the theme against the
commander.

**plan** — The one sentence saying what this deck is trying to do, settled from the
commander and the *theme*. Distinct from the Plan *category*, the *template*'s share of
cards that serve it.
