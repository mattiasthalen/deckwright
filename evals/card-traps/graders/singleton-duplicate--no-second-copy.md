---
# E6: no second copy was kept.
type: regex
target: { source: file, path: deck.html }
pattern: '\n(?:[2-9]|\d{2,}) Sol Ring\b'
match: not_contains
---
