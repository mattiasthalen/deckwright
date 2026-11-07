---
# AC13. Judgement: purpose and target, in template order.
type: llm
focus: trace
---

This is the trace of a deck-building interview for a Commander deck. The template's categories, in order, are Lands (target 38), Ramp (10), Card advantage (12), Targeted disruption (12), Mass disruption (6) and Plan (30). The player worked Lands, then Ramp, then stopped. Judge one thing only: whether the assistant introduced each category it worked, in that order, with its purpose and its target.

PASS if the assistant starts Lands before Ramp, and when starting each it says in a sentence or two what the category is for and states its target (38 for Lands, 10 for Ramp).
FAIL if it starts Ramp before Lands, or starts either without saying what it is for, or without its target.
