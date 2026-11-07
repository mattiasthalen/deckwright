---
# E7. Judgement: a commander that cannot be one.
type: llm
focus: trace
---

This is the trace of a deck-building interview. Asked for a commander, the player said "Llanowar Elves", a creature that is not legendary and so cannot be a commander. Judge one thing only: the assistant's reply to that.

PASS if the assistant tells the player Llanowar Elves cannot be a commander, gives the reason from the card's looked-up type line or text (it is not a legendary creature), and asks whether to keep it anyway or choose another commander.
FAIL if it starts the deck with Llanowar Elves as commander without saying so, says so without asking which the player wants, or gives no reason.
