---
# AC19: the jump landed: Pernicious Deed is under Mass disruption.
type: regex
target: { source: file, path: deck.html }
pattern: 'data-category="Mass disruption"[^>]*>(?:(?!data-category=)[\s\S])*?Pernicious Deed'
---
