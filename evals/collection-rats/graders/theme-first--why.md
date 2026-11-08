---
# C20, why: no assistant message offers a clearly off-theme card as a suggestion (a list item naming it, then a dash or colon and what it does) without saying, somewhere in that message, why it is offered though it is not on the theme (not a Rat, off-theme, no rats here …).
type: regex
target: trace
flags: i
match: not_contains
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?!(?:[^"\\]|\\.)*?(?:(?:\b|(?<=\\n))(?:not|isn\x27t|isn’t|aren\x27t|aren’t|no|non|off|outside|without|doesn\x27t|doesn’t|don\x27t|don’t|neither|nor|never)\W{1,3}(?:\w+\W{1,3}){0,4}?(?:rats?|theme|tribe|tribal)(?:\b|(?<=\\n))|off-theme|non-rat))(?:[^"\\]|\\.)*?\\n\s*(?:[-*•]|\d+[.)])\s+(?:\*\*|__|\[)?(?:Arcane Epiphany|Bellowing Crier|Bitter Triumph|Nocturnal Hunger|Banishing Betrayal|Aetherspouts|Blitzball|Hydro-Channeler|Strixhaven Skycoach|Vampiric Tutor|Splash Lasher)(?:\b|(?<=\\n))(?:\*\*|__|\])?(?:\s*\([^)\\]*\))?\s*(?:—|–|:|-)\s'
---
