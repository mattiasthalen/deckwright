# ADR-0001 — Only the player chooses cards

**Status:** Accepted (2026-11-10)

## Context

Deckwright builds Brawl and Standard decks for Arena with a player who wants to
learn deckbuilding, not to receive a finished list. The first deckwright and the
bare-model analysis showed a model will happily fill a deck when asked to, and
"just fill in the rest" is the request most likely to make it do so.

## Decision

Deckwright is a tutor. It searches, shows cards with reasons, and suggests; the
player chooses every card, every card's category, and every move from the
maybeboard into the deck. This holds under "just fill in the rest": Deckwright
shows each remaining shortlist with its suggested cards marked, and the player
may take them with one word per category. No card enters the deck unseen.
Deckwright never removes a card on its own either, including after a criteria
change that the card now breaks.

Rejected: filling the rest of a deck on request, because a card the player never
saw teaches nothing and makes the deck the model's.

## Consequences

A build takes more turns than a generated list, and the player has to answer for
every category. Outcome check 1 (no card the player did not see and confirm) must
pass in every run. Speed shortcuts are limited to taking marked suggestions in
bulk, one word per category.
