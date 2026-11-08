---
# E17: no question to settle: no assistant sentence speaks of the theme pulling against, clashing or conflicting with the commander and ends in a question mark. A negated mention (nothing pulls against …) is allowed.
type: regex
target: trace
flags: i
match: not_contains
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?<!(?:no|n\x27t|n’t|nothing|without|never|not)\W{1,12}(?:\w+\W{1,3}){0,2})(?:pulls? against|pulling against|clash(?:es)?|conflicts?|at odds|tension|works? against|cuts? against)(?:[^"\\.!?]|\\[^n]){0,200}\?'
---
