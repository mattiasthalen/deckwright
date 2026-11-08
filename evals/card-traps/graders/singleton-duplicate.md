---
# E6: Sol Ring, named twice, is in the deck once.
type: regex
target: { source: file, path: deck.html }
pattern: 'data-section="decklist"[^>]*>(?:(?!data-section=)[\s\S])*?\n1 Sol Ring(?:\s|<)'
---
