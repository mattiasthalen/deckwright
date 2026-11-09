---
# AC29: an available card is offered as "swap it in now?" (swap … in now …?).
type: regex
target: trace
flags: i
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:\b|(?<=\\n))swap(?:\b|(?<=\\n))(?:[^"\\?]|\\[^n]){0,80}?(?:\b|(?<=\\n))in now(?:\b|(?<=\\n))(?:[^"\\?]|\\[^n]){0,80}?\?'
---
