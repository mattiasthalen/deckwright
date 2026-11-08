---
# C28: once the player has said no to cards they don't own (after the assistant's question about them), no later assistant message offers a card labelled not owned in a list item.
type: regex
target: trace
flags: i
match: not_contains
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:don\x27t|don’t|do not) own|not in your collection|aren\x27t in your collection|aren’t in your collection|not[- ]owned|unowned|cards? (?:you\x27re|you’re|you are) missing)(?:[^"\\.!?]|\\[^n]){0,80}\?[\s\S]*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?\\n\s*(?:[-*•]|\d+[.)])\s+(?:\*\*|__|\[)?(?:[^"\\]|\\[^n])*?not owned'
---
