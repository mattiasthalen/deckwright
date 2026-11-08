---
# E5: the player kept it, so it is in the deck.
type: regex
target: { source: file, path: decks/meren-of-clan-nel-toth.html }
pattern: 'data-section="decklist"[^>]*>(?:(?!data-section=)[\s\S])*?\n1 Lightning Bolt(?:\s|<)'
---
