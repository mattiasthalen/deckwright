---
# The deck file the judge read is this calibration's sample: its review has no passage naming the cards counted on a stretch. A run that fails this says nothing about the judge.
type: regex
target: { source: file, path: decks/meren-recursion.json }
pattern: '^(?![\s\S]*counted on a stretch)[\s\S]*The land that makes no mana'
---
