---
# C25, separately: in one assistant message a list item naming a collection card comes before the cards labelled not owned.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?\\n\s*(?:[-*•]|\d+[.)])\s+(?:\*\*|__|\[)?(?:Island|Swamp|Uncharted Haven|Mudflat Village|Lilypad Village|Hidden Grotto|Fabled Passage|Fountainport|Azure Beastbinder|Daggerfang Duo|Lightshell Duo|Mindwhisker|Nightwhorl Hermit|Persistent Marshstalker|Shoreline Looter|Thornplate Intimidator|Thought Shucker|Wick(?:\x27|’|\x27\\\\\x27\x27|\x27\\\"\x27\\\"\x27)s Patrol|Mind Drill Assailant|Tidecaller Mentor|Arcane Epiphany|Bellowing Crier|Bitter Triumph|Feed the Cycle|Nocturnal Hunger|Banishing Betrayal|Aetherspouts|Blitzball|Hydro-Channeler|Strixhaven Skycoach|Vampiric Tutor|Vengeful Bloodwitch|Starscape Cleric|Splash Lasher)(?:\b|(?<=\\n))(?:[^"\\]|\\.)*?not owned'
---
