---
# C20, order: no list of suggestions has a card that clearly does not serve the rats theme before a Rat in the same list (consecutive list items). Only Rat creatures count as serving it here, and only clearly off-theme nonlands as not; cards whose fit is a judgement call are left out of both.
type: regex
target: trace
match: not_contains
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?\\n\s*(?:[-*•]|\d+[.)])\s+(?:\*\*|__|\[)?(?:Arcane Epiphany|Bellowing Crier|Bitter Triumph|Nocturnal Hunger|Banishing Betrayal|Aetherspouts|Blitzball|Hydro-Channeler|Strixhaven Skycoach|Vampiric Tutor|Splash Lasher)(?:\b|(?<=\\n))(?:[^"\\]|\\[^n])*(?:\\n\s*(?:[-*•]|\d+[.)])\s(?:[^"\\]|\\[^n])*)*?\\n\s*(?:[-*•]|\d+[.)])\s+(?:\*\*|__|\[)?(?:Azure Beastbinder|Daggerfang Duo|Lightshell Duo|Mindwhisker|Nightwhorl Hermit|Persistent Marshstalker|Shoreline Looter|Thornplate Intimidator|Thought Shucker|Wick(?:\x27|’|\x27\\\\\x27\x27|\x27\\\"\x27\\\"\x27)s Patrol|Mind Drill Assailant|Tidecaller Mentor)(?:\b|(?<=\\n))'
---
