---
# AC9b, the part a pattern can see: an assistant message ties Vampiric Tutor to Game Changer.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:Vampiric Tutor(?:[^"\\]|\\.){0,300}?game[ -]?changer|game[ -]?changer(?:[^"\\]|\\.){0,300}?Vampiric Tutor)'
---
