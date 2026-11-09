---
# The deck file the judge read is this calibration's sample: its review has no passage on the deck without its commander. A run that fails this says nothing about the judge.
type: regex
target: { source: file, path: decks/meren-recursion.json }
pattern: '^(?![\s\S]*WHEN THE COMMANDER IS ANSWERED)[\s\S]*LANDS THAT MAKE NO MANA\. One: Evolving Wilds'
---
