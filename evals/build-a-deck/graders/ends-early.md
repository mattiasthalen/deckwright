---
# E8: the page renders from what was recorded, the total under 100.
type: regex
target: { source: file, path: deck.html }
pattern: 'data-section="total"[^>]*>(?:(?!data-section=)[\s\S])*?(?<!\d)[1-9]?\d\s*/\s*100(?!\d)'
---
