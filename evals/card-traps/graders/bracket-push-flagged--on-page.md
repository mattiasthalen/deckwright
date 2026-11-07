---
# AC9b, E3: the page names it under the bracket.
type: regex
target: { source: file, path: deck.html }
pattern: 'data-section="bracket"[^>]*>(?:(?!data-section=)[\s\S])*?Vampiric Tutor'
---
