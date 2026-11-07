---
# AC20: a tally runs after Sign in Blood is recorded.
type: regex
target: trace
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\badd\b(?:[^"\\]|\\.)*?Sign in Blood[\s\S]*"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\btally\b'
---
