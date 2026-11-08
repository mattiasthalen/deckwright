---
# C26: no two assistant messages ask (the question itself is --before-recording). One message asks whether to build with cards the player does not own (a question about cards they don't own, not in their collection, or not owned). 20 Island, beyond the 14 owned, is the first yes to more copies than available; Talisman of Dominance, owned not at all, comes after the yes and is not asked about again.
type: regex
target: trace
flags: i
match: not_contains
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:don\x27t|don’t|do not) own|not in your collection|aren\x27t in your collection|aren’t in your collection|not[- ]owned|unowned|cards? (?:you\x27re|you’re|you are) missing)(?:[^"\\.!?]|\\[^n]){0,80}\?[\s\S]*"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:(?:don\x27t|don’t|do not) own|not in your collection|aren\x27t in your collection|aren’t in your collection|not[- ]owned|unowned|cards? (?:you\x27re|you’re|you are) missing)(?:[^"\\.!?]|\\[^n]){0,80}\?'
---
