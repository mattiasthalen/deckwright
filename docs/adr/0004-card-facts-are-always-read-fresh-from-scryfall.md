# ADR-0004 — Card facts are always read fresh from Scryfall

**Status:** Accepted (2026-11-10)

## Context

Legality, what is on Arena and card text change over time, and a model's memory of
them is unreliable. The first deckwright's review drifted when it counted from tags
it had saved itself.

## Decision

Every card Deckwright describes is looked up on Scryfall in that conversation.
Each card in `deck.json` carries its Scryfall id and a copy for display (name,
mana cost, type line, rules text, the date taken); Deckwright never reasons from
the copy. The review looks every card up again and recounts from type line, text,
Scryfall tags and legality, never from saved tags. A changed text is a finding.
When Scryfall is down, Deckwright stops; a card the player insists on is saved as
not checked and blocks approval.

Rejected: a card database shipped with the skill, and reasoning from the saved
copy, because both go stale without anyone noticing.

## Consequences

Every build depends on Scryfall being reachable, and runs must respect its limit
of about ten requests a second. The display copy can be out of date between
reviews; that is visible, not hidden.
