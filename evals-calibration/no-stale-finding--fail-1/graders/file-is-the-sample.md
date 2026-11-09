---
# The deck file the judge read is this calibration's sample: the Kodama's Reach swap comes after the Swamp and answers Lands. A run that fails this says nothing about the judge.
type: regex
target: { source: file, path: decks/meren-recursion.json }
pattern: '"in": "Swamp"[\s\S]*"in": "Kodama''s Reach",\s*"why": "Lands was at 37'
---
