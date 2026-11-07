---
# AC13, the part a pattern can see: an assistant message naming Lands with 38 comes before one naming Ramp with 10.
type: regex
target: trace
pattern: '"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?\bLands\b(?:[^"\\]|\\.)*?\b38\b[\s\S]*?\n[^\n]*"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?\bRamp\b(?:[^"\\]|\\.)*?\b10\b'
---
