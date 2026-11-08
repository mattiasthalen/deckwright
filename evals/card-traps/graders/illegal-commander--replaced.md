---
# E7: the player chose another, and the page's commander is Meren.
type: regex
target: { source: file, path: decks/meren-of-clan-nel-toth.html }
pattern: 'data-section="commander"[^>]*>(?:(?!data-section=)[\s\S])*?Meren of Clan Nel Toth'
---
