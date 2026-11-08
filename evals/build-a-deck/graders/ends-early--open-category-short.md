---
# E8: a category never worked shows 0 against its target.
type: regex
target: { source: file, path: deck.html }
pattern: 'data-category="Targeted disruption"[^>]*>(?:(?!data-category=)[\s\S])*?(?<!\d)0\s*/\s*12(?!\d)'
---
