---
# AC24, the part a pattern can see: the written review stored in the deck file names Evolving Wilds.
type: regex
target: { source: file, path: decks/meren-recursion.json }
pattern: '"review"\s*:\s*\{[\s\S]*?"text"\s*:\s*"(?:[^"\\]|\\.)*?Evolving Wilds'
---
