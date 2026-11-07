---
# AC20: no Lands count against its target is shown before the script has tallied anything.
type: regex
target: trace
match: not_contains
pattern: '^(?:(?!"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\btally\b)[\s\S])*?"role":"assistant"[^\n]*"type":"text","text":"(?:[^"\\]|\\.)*?\b\d+\s*/\s*38\b'
---
