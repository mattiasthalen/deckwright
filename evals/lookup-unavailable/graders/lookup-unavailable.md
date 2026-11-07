---
# E2. Judgement: a lookup that cannot reach Scryfall.
type: llm
focus: trace
---

This is the trace of a deck-building interview in which the card lookup could not reach Scryfall. The player asked to add Sol Ring. Judge one thing only: the assistant's reply when the lookup of Sol Ring failed.

PASS if the assistant says it could not reach Scryfall (or could not look the card up), names Sol Ring, asks the player for the card's text, and says nothing about what Sol Ring does until the player has given that text.
FAIL if it describes Sol Ring (its cost, what it does, which category it counts in) before the player gives the text, or records it without asking, or does not say the lookup failed.
