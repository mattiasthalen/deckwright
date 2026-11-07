---
# AC9b, the part a pattern can see: an assistant message names Vampiric Tutor and, within 900 characters of it, calls something a Game Changer (not "not a Game Changer", which is said of Sol Ring).
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:Vampiric Tutor(?:[^"\\]|\\.){0,900}?(?<!(?:\bnot|n''t|n’t|\bno)\s+(?:an?\s+|one of the\s+)?)game[ -]?changer|(?<!(?:\bnot|n''t|n’t|\bno)\s+(?:an?\s+|one of the\s+)?)game[ -]?changer(?:[^"\\]|\\.){0,900}?Vampiric Tutor)'
---
