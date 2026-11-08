---
# AC19: the page shows Ramp against 8.
type: regex
target: { source: file, path: decks/meren-of-clan-nel-toth.html }
pattern: 'data-category="Ramp"[^>]*>(?:(?!data-category=)[\s\S])*?(?<!\d)\d+\s*/\s*8(?!\d)'
---
