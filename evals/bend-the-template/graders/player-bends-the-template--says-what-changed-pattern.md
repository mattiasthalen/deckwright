---
# AC19, the part a pattern can see: after the change an assistant message names Ramp with 8.
type: regex
target: trace
flags: i
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\btarget\b(?:[^"\\]|\\.)*?[Rr]amp(?:[^"\\]|\\.)*?\b8\b[\s\S]*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?(?:\bramp\b(?:[^"\\]|\\.)*?\b8\b|\b8\b(?:[^"\\]|\\.)*?\bramp\b)'
---
