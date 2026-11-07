---
# AC19: a tally after the change reports Ramp's target as 8 (the tally's JSON, as it appears escaped in the trace).
type: regex
target: trace
pattern: '"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\btarget\b(?:[^"\\]|\\.)*?[Rr]amp(?:[^"\\]|\\.)*?\b8\b[\s\S]*"name":"Bash","input":\{"command":"(?:[^"\\]|\\.)*?deck\.py(?:[^"\\]|\\.)*?\btally\b[\s\S]*?(?:\\"name\\":\s*\\"Ramp\\"[^{}]*?\\"target\\":\s*8\b|\\"target\\":\s*8\b[^{}]*?\\"name\\":\s*\\"Ramp\\")'
---
