---
# E6: Sol Ring, named twice, is in the deck once.
type: regex
target: { source: file, path: decks/meren-of-clan-nel-toth.html }
pattern: 'data-section="decklist"[^>]*>(?:(?!data-section=)[\s\S])*?\n1 Sol Ring(?:\s|<)'
---
