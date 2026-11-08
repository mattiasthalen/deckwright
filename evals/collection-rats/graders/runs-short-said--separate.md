---
# C25, separately: a list item naming a collection card comes before a list labelled not owned (as in `runs-short-said`), in the same message or a later one, with no `add` between.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?\\n\s*(?:[-*•]|\d+[.)])\s+(?:\*\*|__|\[)?(?:Island|Swamp|Uncharted Haven|Mudflat Village|Lilypad Village|Hidden Grotto|Fabled Passage|Fountainport|Azure Beastbinder|Daggerfang Duo|Lightshell Duo|Mindwhisker|Nightwhorl Hermit|Persistent Marshstalker|Shoreline Looter|Thornplate Intimidator|Thought Shucker|Wick(?:\x27|’|\x27\\\\\x27\x27|\x27\\\"\x27\\\"\x27)s Patrol|Mind Drill Assailant|Tidecaller Mentor|Arcane Epiphany|Bellowing Crier|Bitter Triumph|Feed the Cycle|Nocturnal Hunger|Banishing Betrayal|Aetherspouts|Blitzball|Hydro-Channeler|Strixhaven Skycoach|Vampiric Tutor|Vengeful Bloodwitch|Starscape Cleric|Splash Lasher)(?:\b|(?<=\\n))(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))add(?:\b|(?<=\\n)))[\s\S])*?(?:\b|(?<=\\n))(?:not owned|(?:don''t|don’t|do not) own)(?:\b|(?<=\\n))(?:[^"\\]|\\[^n]){0,200}?\\n(?:\\n|\s)*(?:[-*•]|\d+[.)])\s'
---
