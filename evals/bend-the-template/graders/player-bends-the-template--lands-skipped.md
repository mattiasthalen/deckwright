---
# AC19: Lands was skipped, so it stands at 0 of 38.
type: regex
target: { source: file, path: deck.html }
pattern: 'data-category="Lands"[^>]*>(?:(?!data-category=)[\s\S])*?(?<!\d)0\s*/\s*38(?!\d)'
---
