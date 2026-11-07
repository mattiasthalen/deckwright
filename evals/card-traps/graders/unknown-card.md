---
# E1. Judgement: a misspelt card.
type: llm
focus: trace
---

This is the trace of a deck-building interview. The player said "Add Vampiric Tutr", a misspelling; Scryfall has no card of that name, and its closest match is Vampiric Tutor. Judge one thing only: the assistant's reply to that.

PASS if the assistant says no card by that exact name was found, names Vampiric Tutor as the closest match, and asks the player to confirm before recording it.
FAIL if it records Vampiric Tutor without saying the name did not match, or records a card without asking, or describes a card it did not look up.
