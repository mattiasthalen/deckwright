---
# AC34, AC16: the page rendered at the end is a finished deck's: no unfinished mark.
type: regex
target: { source: file, path: decks/meren-recursion.html }
match: not_contains
pattern: 'data-section="unfinished"'
---
