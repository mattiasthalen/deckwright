---
# E5: recorded on the player's yes, and flagged on the page.
type: regex
target: { source: file, path: deck.html }
pattern: 'data-section="checks"[^>]*>(?:(?!data-section=)[\s\S])*?Lightning Bolt'
---
