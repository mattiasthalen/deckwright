---
# AC29: on a deck built with "not owned: no", no card the player does not own goes in by swap: every swap's IN is an owned extra or a basic land.
type: regex
target: trace
flags: i
match: not_contains
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+swap(?:\b|(?<=\\n))(?:\s+--deck\s+\S+)?\s+''(?:[^'']|''\\\\'''')*''\s+''(?!(?:Satyr Wayfinder|Wood Elves|Farhaven Elf|Rampant Growth|Kodama(?:''|''\\\\''''|’)s Reach|Burnished Hart|Mind Stone|Fellwar Stone|Commander(?:''|''\\\\''''|’)s Sphere|Explosive Vegetation|Swamp|Forest)'')'
---
