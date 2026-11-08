# ADR-0001 — Compute in a script shipped with the skill; judge in the skill

**Status:** Accepted (2026-11-07)

## Context

deckwright's rule is that anything that can be deterministic is. Card facts, counts
against targets, the deck checks and the deck page are computable; suggestions,
critique and which category a card serves are judgement. deckwright must work in
regular claude.ai chat, mobile included. There, code execution runs Python 3.13 with
uv, package installs pass the allowlist, and a script reached api.scryfall.com directly (measured on the owner's account,
2026-11-07).

## Decision

deckwright is a Claude plugin. Each skill ships a script, run with uv, that does every
computable part: looking up card facts, recording the deck, counting and checking it,
and rendering the deck page. The skill holds the judgement and calls the script for
everything else. Templates are plain files inside the skill folder, so a skill also
works uploaded on its own. deckwright requires code execution.

Rejected:

- No code, Claude counting and checking: works everywhere, but is not deterministic.
- JavaScript inside the deck page doing the counting: rejected by the owner.
- A script with a no-code fallback for counting: two ways to count that drift apart.
- Templates in a top-level folder: the skill could not be uploaded alone.

## Consequences

The same deck always gives the same counts, checks and page. A player without code
execution cannot use deckwright, and the README says so. Where the script cannot reach
Scryfall, the player supplies the card's text, and the page marks those cards.
