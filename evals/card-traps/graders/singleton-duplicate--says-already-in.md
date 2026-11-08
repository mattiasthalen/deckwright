---
# E6: deckwright says Sol Ring is already in.
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:Sol Ring(?:[^"\\]|\\.){0,200}?already|already(?:[^"\\]|\\.){0,200}?Sol Ring)'
---
