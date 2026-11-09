---
# AC29: an available card is offered as a swap, never for the maybeboard: no maybeboard add of an owned extra.
type: regex
target: trace
flags: i
match: not_contains
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+maybeboard(?:\s+--deck\s+\S+)?\s+add(?:\b|(?<=\\n))(?:\s+--deck\s+\S+)?\s+''(?:Satyr Wayfinder|Wood Elves|Farhaven Elf|Rampant Growth|Kodama(?:''|''\\\\''''|’)s Reach|Burnished Hart|Mind Stone|Fellwar Stone|Commander(?:''|''\\\\''''|’)s Sphere|Explosive Vegetation)'''
---
