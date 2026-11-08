---
# C28: no add records a card the collection does not hold: every card the script adds is one of the collection's (names quoted, as the skill quotes them).
type: regex
target: trace
match: not_contains
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))(?:add)(?:\b|(?<=\\n))(?:\s+--\S+(?:\s+(?:''[^'']*''|\S+))?)*\s+(?:''|\\\")(?!(?:Aetherspouts|Arcane Epiphany|Azure Beastbinder|Bakersbane Duo|Banishing Betrayal|Bellowing Crier|Bitter Triumph|Blitzball|Daggerfang Duo|Fabled Passage|Feed the Cycle|Fountainport|Hidden Grotto|Hydro-Channeler|Island|Lightshell Duo|Lilypad Village|Mind Drill Assailant|Mindwhisker|Moonrise Cleric|Mountain|Mudflat Village|Nightwhorl Hermit|Nocturnal Hunger|Persistent Marshstalker|Plains|Shoreline Looter|Splash Lasher|Starscape Cleric|Strixhaven Skycoach|Swamp|Thornplate Intimidator|Thought Shucker|Tidecaller Mentor|Uncharted Haven|Vampiric Tutor|Vengeful Bloodwitch|Vren, the Relentless|Wick(?:\x27|’|\x27\\\\\x27\x27|\x27\\\"\x27\\\"\x27)s Patrol|Wick, the Whorled Mind|Zoraline, Cosmos Caller)(?:''|\\\"))'
---
