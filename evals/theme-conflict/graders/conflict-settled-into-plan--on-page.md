---
# C23: the deck page shows the plan sentence, which speaks of squirrels or raccoons.
type: regex
target: { source: file, path: decks/trash-pandas.html }
flags: i
pattern: 'data-section="plan"[^>]*>(?:(?!data-section=)[\s\S])*?(?:squirrel|raccoon)'
---
