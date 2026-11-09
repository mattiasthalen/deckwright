---
# AC30: on a deck built with "not owned: yes", a card the player does not own goes in by swap: a swap whose IN is none of the cards collection.txt holds beside the deck (every card of the deck is owned, so an IN cannot be one of them).
type: tool_used
tool: Bash
input_match: '"command":"(?:[^"\\]|\\.)*?deck\.py(?:''|\\\")?\s+swap(?:\b|(?<=\\n))(?:\s+--deck\s+\S+)?\s+''(?:[^'']|''\\\\'''')*''\s+''(?!(?:Satyr Wayfinder|Wood Elves|Farhaven Elf|Rampant Growth|Kodama(?:''|''\\\\''''|’)s Reach|Burnished Hart|Mind Stone|Fellwar Stone|Commander(?:''|''\\\\''''|’)s Sphere|Explosive Vegetation|Demonic Tutor|Lightning Bolt|Swamp|Forest)'')'
min: 1
---
