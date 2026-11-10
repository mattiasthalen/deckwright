---
# AC20: asked for the page mid-build, the skill renders it, and the page carries the unfinished mark: the total of 100 and that it was not reviewed.
type: regex
target: { source: file, path: decks/rat-pack.html }
flags: i
pattern: 'data-section="unfinished"[^>]*>(?:(?!data-section=)[\s\S])*?(?<!\d)\d{1,2}\s+of\s+100,\s*not reviewed'
---
