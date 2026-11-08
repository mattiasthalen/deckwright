---
# E8: the page renders from what was recorded, the total under 100.
type: regex
target: { source: file, path: decks/meren-of-clan-nel-toth.html }
pattern: 'data-section="total"[^>]*>(?:(?!data-section=)[\s\S])*?(?<!\d)[1-9]?\d\s*/\s*100(?!\d)'
---
