---
# C28: the player's yes to a card not owned is met with the question, which the no answers.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:don\x27t|don’t|do not) own|not in your collection|aren\x27t in your collection|aren’t in your collection|not[- ]owned|unowned|cards? (?:you\x27re|you’re|you are) missing)(?:[^"\\.!?]|\\[^n]){0,80}\?'
---
