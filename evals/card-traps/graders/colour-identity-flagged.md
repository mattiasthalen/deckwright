---
# E5: recorded on the player's yes, and flagged on the page.
type: regex
target: { source: file, path: decks/meren-of-clan-nel-toth.html }
pattern: 'data-section="checks"[^>]*>(?:(?!data-section=)[\s\S])*?Lightning Bolt'
---
