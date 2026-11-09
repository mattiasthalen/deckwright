---
# AC37: the page shows the deck at its deck size: 100 / 100.
type: regex
target: { source: file, path: decks/meren-recursion.html }
pattern: 'data-section="total"[^>]*>(?:(?!data-section=)[\s\S])*?(?<!\d)100\s*/\s*100(?!\d)'
---
