---
# AC30: the page marks it not owned. Every card the deck started with is owned, so a card with copies not owned in the ownership section is one swapped in.
type: regex
target: { source: file, path: decks/meren-recursion.html }
flags: i
pattern: 'data-section="ownership"[^>]*>(?:(?!data-section=)[\s\S])*?(?<![\d])[1-9]\d*\s+not owned'
---
