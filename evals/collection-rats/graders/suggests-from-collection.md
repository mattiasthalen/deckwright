---
# C19: an assistant message says its suggestions are from the player's collection (your collection, you own, you have) within 300 characters before a list item naming a card from the narrowing.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:your collection|you own|you have|owned by you|in your binders?|from your cards)(?:[^"\\]|\\.){0,300}?\\n\s*(?:[-*•]|\d+[.)])\s+(?:\*\*|__|\[)?(?:Island|Swamp|Uncharted Haven|Mudflat Village|Lilypad Village|Hidden Grotto|Fabled Passage|Fountainport|Azure Beastbinder|Daggerfang Duo|Lightshell Duo|Mindwhisker|Nightwhorl Hermit|Persistent Marshstalker|Shoreline Looter|Thornplate Intimidator|Thought Shucker|Wick(?:\x27|’|\x27\\\\\x27\x27|\x27\\\"\x27\\\"\x27)s Patrol|Mind Drill Assailant|Tidecaller Mentor|Arcane Epiphany|Bellowing Crier|Bitter Triumph|Feed the Cycle|Nocturnal Hunger|Banishing Betrayal|Aetherspouts|Blitzball|Hydro-Channeler|Strixhaven Skycoach|Vampiric Tutor|Vengeful Bloodwitch|Starscape Cleric|Splash Lasher)(?:\b|(?<=\\n))'
---
