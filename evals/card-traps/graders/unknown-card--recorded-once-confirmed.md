---
# E1: once confirmed, the real card is in the deck.
type: regex
target: { source: file, path: deck.html }
pattern: 'data-section="decklist"[^>]*>(?:(?!data-section=)[\s\S])*?\n1 Vampiric Tutor(?:\s|<)'
---
